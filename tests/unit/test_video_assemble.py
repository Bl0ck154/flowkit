"""Tests for Phase 3: concat/finalize endpoints, target_duration_s,
thumbnail/TTS provider routing.

pytest-asyncio runs in AUTO mode (see pytest.ini).
"""
import subprocess
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api import projects as projects_api
from agent.api import tts as tts_api
from agent.api.videos import router as videos_router
from agent.db import crud
from agent.sdk.services.provider_base import (
    KIND_AUDIO,
    KIND_IMAGE,
    MediaProvider,
    ProviderCapabilities,
)


@pytest.fixture
def videos_client(test_db):
    app = FastAPI()
    app.include_router(videos_router, prefix="/api")
    return TestClient(app, raise_server_exceptions=False)


def _make_clip(path: Path, duration: float = 1.0, size: str = "320x240") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=red:s={size}:d={duration}:r=30",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(path)],
        capture_output=True, check=True, timeout=60)


async def _mk_video_with_clips(tmp_path, n_scenes=3, orientation="VERTICAL",
                               target_duration_s=None, clip_duration=1.0):
    proj = await crud.create_project(name="Assemble Test")
    video = await crud.create_video(
        project_id=proj["id"], title="Ep 1", orientation=orientation,
        target_duration_s=target_duration_s)
    key = f"{orientation.lower()}_video_url"
    for i in range(n_scenes):
        scene = await crud.create_scene(
            video_id=video["id"], display_order=i, prompt=f"scene {i}")
        clip = tmp_path / f"scene_{i}.mp4"
        _make_clip(clip, duration=clip_duration)
        await crud.update_scene(scene["id"], **{key: f"file://{clip}"})
    return proj, video


# ---------------------------------------------------------------------------
# target_duration_s persistence
# ---------------------------------------------------------------------------

async def test_target_duration_s_roundtrip(test_db):
    proj = await crud.create_project(name="P")
    v = await crud.create_video(project_id=proj["id"], title="V",
                                target_duration_s=60.0)
    assert v["target_duration_s"] == 60.0
    v2 = await crud.update_video(v["id"], target_duration_s=30.0)
    assert v2["target_duration_s"] == 30.0
    assert (await crud.get_video(v["id"]))["target_duration_s"] == 30.0


# ---------------------------------------------------------------------------
# concat / finalize
# ---------------------------------------------------------------------------

async def test_concat_merges_and_trims(videos_client, test_db, tmp_path):
    _, video = await _mk_video_with_clips(
        tmp_path, n_scenes=3, target_duration_s=2.5)

    r = videos_client.post(f"/api/videos/{video['id']}/concat",
                           json={"orientation": "VERTICAL"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scenes_used"] == 3
    assert body["scenes_missing"] == []
    assert body["trimmed"] is True  # 3s of clips trimmed to 2.5s target
    assert abs(body["duration"] - 2.5) < 0.3
    assert Path(body["output_path"]).is_file()

    row = await crud.get_video(video["id"])
    assert row["vertical_url"].startswith("file://")
    assert abs(row["duration"] - 2.5) < 0.3
    assert row["target_duration_s"] == 2.5


async def test_concat_no_target_keeps_full_length(videos_client, test_db, tmp_path):
    _, video = await _mk_video_with_clips(tmp_path, n_scenes=2)

    r = videos_client.post(f"/api/videos/{video['id']}/concat", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trimmed"] is False
    assert abs(body["duration"] - 2.0) < 0.3


async def test_concat_request_target_overrides_stored(videos_client, test_db, tmp_path):
    _, video = await _mk_video_with_clips(
        tmp_path, n_scenes=3, target_duration_s=99.0)

    r = videos_client.post(f"/api/videos/{video['id']}/concat",
                           json={"target_duration_s": 1.5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trimmed"] is True
    assert abs(body["duration"] - 1.5) < 0.3
    row = await crud.get_video(video["id"])
    assert row["target_duration_s"] == 1.5


async def test_concat_missing_scenes_400(videos_client, test_db):
    proj = await crud.create_project(name="P3")
    video = await crud.create_video(project_id=proj["id"], title="V3",
                                    orientation="VERTICAL")
    await crud.create_scene(video_id=video["id"], display_order=0, prompt="x")
    r = videos_client.post(f"/api/videos/{video['id']}/concat", json={})
    assert r.status_code == 400


async def test_finalize_marks_completed(videos_client, test_db, tmp_path):
    _, video = await _mk_video_with_clips(tmp_path, n_scenes=2)

    r = videos_client.post(f"/api/videos/{video['id']}/finalize",
                           json={"orientation": "VERTICAL",
                                 "target_duration_s": 1.5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "COMPLETED"
    assert "concat (2 scenes)" in body["steps"]
    assert Path(body["output_path"]).is_file()

    row = await crud.get_video(video["id"])
    assert row["status"] == "COMPLETED"


async def test_finalize_404(videos_client, test_db):
    r = videos_client.post("/api/videos/nope/finalize", json={})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# thumbnail via provider
# ---------------------------------------------------------------------------

class _FakeThumbProvider(MediaProvider):
    name = "assistant"
    capabilities = ProviderCapabilities()

    def __init__(self, image_url: str):
        self.jobs = []
        self.image_url = image_url

    async def run(self, job):
        self.jobs.append(job)
        mid = "550e8400-e29b-41d4-a716-446655440000"
        return {"data": {"media": [{"name": mid,
                                    "image": {"generatedImage": {
                                        "mediaId": mid,
                                        "fifeUrl": self.image_url}}}]}}


@pytest.fixture
def projects_client(test_db, tmp_path, monkeypatch):
    src = tmp_path / "thumb_src.png"
    src.write_bytes(b"\x89PNG fake")
    fake = _FakeThumbProvider(image_url=f"file://{src}")

    class FakeRegistry:
        def get(self, name):
            return fake if name == "assistant" else None

        def names(self):
            return ["assistant"]

    class FakeOps:
        registry = FakeRegistry()

    monkeypatch.setattr("agent.sdk.services.operations.get_operations", lambda: FakeOps())

    app = FastAPI()
    app.include_router(projects_api.router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)
    client.fake_provider = fake
    return client


async def test_thumbnail_via_provider(projects_client, test_db):
    proj = await crud.create_project(name="Thumb Proj")

    r = projects_client.post(
        f"/api/projects/{proj['id']}/generate-thumbnail",
        json={"prompt": "epic thumbnail", "provider": "assistant"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert Path(body["output_path"]).is_file()

    job = projects_client.fake_provider.jobs[0]
    assert job.kind == KIND_IMAGE
    assert job.orientation == "HORIZONTAL"  # LANDSCAPE default
    assert "epic thumbnail" in job.prompt


async def test_thumbnail_unknown_provider_400(projects_client, test_db):
    proj = await crud.create_project(name="P")
    r = projects_client.post(
        f"/api/projects/{proj['id']}/generate-thumbnail",
        json={"prompt": "x", "provider": "nope"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# TTS via provider
# ---------------------------------------------------------------------------

class _FakeTTSProvider(MediaProvider):
    name = "assistant"
    capabilities = ProviderCapabilities(generate_audio=True)

    def __init__(self):
        self.jobs = []

    async def run(self, job):
        self.jobs.append(job)
        return {"data": {"url": "file:///tmp/fake_tts.wav",
                         "audio_path": "/tmp/fake_tts.wav"}}

    def check(self, job):
        if job.kind == KIND_AUDIO:
            return None
        return super().check(job)


@pytest.fixture
def tts_client(test_db, monkeypatch):
    fake = _FakeTTSProvider()

    class FakeRegistry:
        def get(self, name):
            return fake if name == "assistant" else None

        def names(self):
            return ["assistant"]

    class FakeOps:
        registry = FakeRegistry()

    monkeypatch.setattr("agent.sdk.services.operations.get_operations", lambda: FakeOps())

    app = FastAPI()
    app.include_router(tts_api.router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)
    client.fake_provider = fake
    return client


async def test_tts_via_provider(tts_client, test_db):
    r = tts_client.post("/api/tts/generate",
                        json={"text": "hello world", "provider": "assistant"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["audio_path"] == "/tmp/fake_tts.wav"
    job = tts_client.fake_provider.jobs[0]
    assert job.kind == KIND_AUDIO
    assert job.prompt == "hello world"


async def test_tts_unknown_provider_400(tts_client, test_db):
    r = tts_client.post("/api/tts/generate",
                        json={"text": "hi", "provider": "nope"})
    assert r.status_code == 400


async def test_tts_flow_provider_rejected(tts_client, test_db, monkeypatch):
    """A provider without audio capability is rejected with 400."""
    from agent.sdk.services.provider_base import MediaProvider as MP

    class Flowish(MP):
        name = "flow"
        capabilities = ProviderCapabilities()  # generate_audio=False

        async def run(self, job):
            raise AssertionError("must not run")

    class FakeRegistry:
        def get(self, name):
            return Flowish() if name == "flow" else None

        def names(self):
            return ["flow"]

    class FakeOps:
        registry = FakeRegistry()

    monkeypatch.setattr("agent.sdk.services.operations.get_operations", lambda: FakeOps())
    r = tts_client.post("/api/tts/generate",
                        json={"text": "hi", "provider": "flow"})
    assert r.status_code == 400
