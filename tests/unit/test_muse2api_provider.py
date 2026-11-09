"""Tests for the muse2api media provider (HTTP gateway to muse.ai).

The gateway is faked with httpx.MockTransport, so these run offline and pin
the wire contract: paths, bearer auth, the payload fields, task polling, and
the OpenAI error body.
"""
import base64
import json

import httpx
import pytest

from agent.sdk.services import muse2api_provider as mp
from agent.sdk.services.provider_base import (
    KIND_EDIT_IMAGE,
    KIND_IMAGE,
    KIND_UPSCALE,
    KIND_VIDEO,
    KIND_VIDEO_REFS,
    ProviderJob,
)
from agent.sdk.services.registry import ProviderRegistry
from agent.sdk.services.result_handler import parse_result
from agent.services.muse2api_client import Muse2APIClient
from agent.worker._parsing import _is_uuid

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 8
BASE = "http://muse.test"


class FakeGateway:
    """Minimal muse2api: images, video tasks that finish after N polls, media."""

    def __init__(self, polls_until_done=2, video_status="succeeded", key="k"):
        self.polls_until_done = polls_until_done
        self.video_status = video_status
        self.key = key
        self.calls: list[tuple[str, str, dict | None]] = []
        self._polls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, request.url.path, body))
        path = request.url.path
        if path.startswith("/v1/media/"):
            return httpx.Response(200, content=MP4, headers={"content-type": "video/mp4"})
        if request.headers.get("authorization") != f"Bearer {self.key}":
            return httpx.Response(401, json={"error": {
                "message": "invalid or missing API key", "type": "authentication_error",
                "code": "invalid_api_key"}})
        if path == "/v1/images/generations":
            return httpx.Response(200, json={"created": 1, "data": [
                {"b64_json": base64.b64encode(PNG).decode(), "revised_prompt": None}]})
        if path == "/v1/videos" and request.method == "POST":
            return httpx.Response(200, json={"id": "task_1", "status": "queued"})
        if path == "/v1/videos/task_1":
            self._polls += 1
            if self._polls < self.polls_until_done:
                return httpx.Response(200, json={"id": "task_1", "status": "running"})
            if self.video_status != "succeeded":
                return httpx.Response(200, json={"id": "task_1", "status": self.video_status,
                                                 "error": "upstream refused", "result": None})
            return httpx.Response(200, json={"id": "task_1", "status": "succeeded", "result": {
                "url": f"{BASE}/v1/media/vid_abc.mp4", "mime": "video/mp4"}})
        return httpx.Response(404, json={"error": {"message": "nope", "code": "not_found"}})


@pytest.fixture
def gateway():
    return FakeGateway()


@pytest.fixture
def provider(tmp_path, gateway, monkeypatch):
    monkeypatch.setattr(mp.config, "MUSE2API_ALLOW_DEGRADED", False)
    client = Muse2APIClient(BASE, "k", timeout_s=5, poll_s=0.01,
                            transport=httpx.MockTransport(gateway))
    prov = mp.Muse2APIProvider(client)
    prov.output_dir = tmp_path / "muse2api"
    return prov


@pytest.fixture
def start_image(tmp_path):
    p = tmp_path / "start.png"
    p.write_bytes(PNG)
    return "file://" + str(p)


async def test_image_is_saved_locally_with_minted_uuid(provider, gateway, start_image):
    job = ProviderJob(job_id="img1", kind=KIND_IMAGE, prompt="a fox",
                      orientation="HORIZONTAL", reference_urls=(start_image,),
                      extra={"composition": "wide establishing shot"})
    result = await provider.run(job)

    gen = parse_result(result, "GENERATE_IMAGE")
    assert gen.success, result
    assert _is_uuid(gen.media_id)
    assert gen.url.startswith("file://") and gen.url.replace("\\", "/").endswith("/muse2api/img1.png")
    assert (provider.output_dir / "img1.png").read_bytes() == PNG

    method, path, body = gateway.calls[0]
    assert (method, path) == ("POST", "/v1/images/generations")
    assert body["size"] == "16:9"
    assert body["model"] == "muse-image"
    assert body["response_format"] == "b64_json"
    assert "wide establishing shot" in body["prompt"]
    assert body["image"] == ["data:image/png;base64," + base64.b64encode(PNG).decode()]


async def test_image_without_refs_sends_no_image_field(provider, gateway):
    job = ProviderJob(job_id="img2", kind=KIND_IMAGE, prompt="a fox", orientation="VERTICAL")
    assert parse_result(await provider.run(job), "GENERATE_IMAGE").success
    assert "image" not in gateway.calls[0][2]


async def test_image_refs_are_deduped_and_capped_at_four(provider, gateway, tmp_path):
    refs = []
    for i in range(6):
        p = tmp_path / f"ref{i}.png"
        p.write_bytes(PNG + bytes([i]))
        refs.append("file://" + str(p))
    job = ProviderJob(job_id="img3", kind=KIND_IMAGE, prompt="a fox",
                      orientation="VERTICAL", reference_urls=(refs[0], refs[0], *refs[1:]))
    assert parse_result(await provider.run(job), "GENERATE_IMAGE").success

    sent = gateway.calls[0][2]["image"]
    assert len(sent) == 4
    assert sent == ["data:image/png;base64," + base64.b64encode(PNG + bytes([i])).decode()
                    for i in range(4)]


async def test_unreadable_ref_fails_the_job_instead_of_dropping_the_character(provider, gateway):
    job = ProviderJob(job_id="img4", kind=KIND_IMAGE, prompt="a fox",
                      orientation="VERTICAL", reference_urls=("file:///no/such/ref.png",))
    result = await provider.run(job)
    assert "error" in result and "ref.png" in result["error"]
    assert gateway.calls == []


async def test_unreachable_http_ref_fails_the_job(provider, gateway, monkeypatch):
    async def boom(ref, **_):
        raise httpx.ConnectError("no route", request=httpx.Request("GET", ref))
    monkeypatch.setattr(mp, "to_data_url", boom)
    job = ProviderJob(job_id="img5", kind=KIND_IMAGE, prompt="a fox",
                      orientation="VERTICAL", reference_urls=("https://cdn.test/ref.png",))
    result = await provider.run(job)
    assert result["error"].startswith("muse2api: ")
    assert gateway.calls == []


async def test_video_sends_first_frame_inline_and_polls(provider, gateway, start_image):
    job = ProviderJob(job_id="vid1", kind=KIND_VIDEO, prompt="fox runs",
                      orientation="VERTICAL", start_url=start_image)
    result = await provider.run(job)

    gen = parse_result(result, "GENERATE_VIDEO")
    assert gen.success, result
    assert _is_uuid(gen.media_id)
    assert (provider.output_dir / "vid1.mp4").read_bytes() == MP4

    create = next(c for c in gateway.calls if c[:2] == ("POST", "/v1/videos"))
    body = create[2]
    assert body["size"] == "9:16"
    assert body["seconds"] == 8
    assert body["image"] == "data:image/png;base64," + base64.b64encode(PNG).decode()
    polls = [c for c in gateway.calls if c[1] == "/v1/videos/task_1"]
    assert len(polls) == 2


async def test_failed_video_task_surfaces_gateway_error(tmp_path, start_image):
    gw = FakeGateway(polls_until_done=1, video_status="failed")
    client = Muse2APIClient(BASE, "k", timeout_s=5, poll_s=0.01,
                            transport=httpx.MockTransport(gw))
    prov = mp.Muse2APIProvider(client)
    prov.output_dir = tmp_path
    result = await prov.run(ProviderJob(job_id="v", kind=KIND_VIDEO, prompt="p",
                                        start_url=start_image))
    assert "upstream refused" in result["error"]


async def test_openai_error_body_is_reported(tmp_path):
    client = Muse2APIClient(BASE, "wrong", transport=httpx.MockTransport(FakeGateway()))
    prov = mp.Muse2APIProvider(client)
    prov.output_dir = tmp_path
    result = await prov.run(ProviderJob(job_id="i", kind=KIND_IMAGE, prompt="p"))
    assert result["error"] == "muse2api invalid_api_key (HTTP 401): invalid or missing API key"


async def test_chained_video_fails_loudly_unless_degraded(provider, gateway, start_image):
    job = ProviderJob(job_id="c", kind=KIND_VIDEO, prompt="p",
                      start_url=start_image, end_url=start_image)
    result = await provider.run(job)
    assert "end-frame" in result["error"]
    assert gateway.calls == []

    provider.allow_degraded = True
    result = await provider.run(job)
    assert parse_result(result, "GENERATE_VIDEO").success


async def test_video_without_start_frame_errors(provider):
    result = await provider.run(ProviderJob(job_id="n", kind=KIND_VIDEO, prompt="p"))
    assert result == {"error": "No vertical image for scene"}


def test_capabilities_and_checks(provider, monkeypatch):
    assert provider.check(ProviderJob(job_id="a", kind=KIND_IMAGE)) is None
    assert provider.check(ProviderJob(job_id="a", kind=KIND_VIDEO)) is None
    for kind in (KIND_EDIT_IMAGE, KIND_UPSCALE):
        assert "does not support" in provider.check(ProviderJob(job_id="a", kind=kind))
    assert "MUSE2API_ALLOW_DEGRADED" in provider.check(
        ProviderJob(job_id="a", kind=KIND_VIDEO_REFS))

    monkeypatch.setattr(mp.config, "MUSE2API_ALLOW_DEGRADED", True)
    degraded = mp.Muse2APIProvider(provider.client)
    assert degraded.capabilities.generate_video_r2v
    assert degraded.check(ProviderJob(job_id="a", kind=KIND_VIDEO_REFS)) is None


def test_unconfigured_provider_is_unavailable():
    prov = mp.Muse2APIProvider(Muse2APIClient(""))
    assert not prov.is_available()
    assert "MUSE2API_URL" in prov.check(ProviderJob(job_id="a", kind=KIND_IMAGE))


async def test_register_existing_image_mints_uuid(provider, start_image):
    result = await provider.register_existing_image(start_image, name="Fox")
    mid = result["data"]["media"][0]["name"]
    assert _is_uuid(mid)
    assert result["data"]["url"] == start_image

    missing = await provider.register_existing_image("file:///nope.png", name="Fox")
    assert "not found" in missing["error"]


def test_registry_includes_muse2api():
    registry = ProviderRegistry(flow_client=None)
    assert isinstance(registry.get("muse2api"), mp.Muse2APIProvider)
    names = [p["name"] for p in registry.status()]
    assert "muse2api" in names
