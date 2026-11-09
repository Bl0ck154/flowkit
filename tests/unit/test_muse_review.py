"""Tests for agent self-review (`muse` provider): contact sheets -> hand scoring -> submit.

pytest-asyncio runs in AUTO mode (see pytest.ini).
"""
import subprocess
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api import reviews as reviews_api
from agent.db import crud
from agent.services.video_reviewer import (
    prepare_review_sheets,
    score_review_answer,
)


@pytest.fixture
def reviews_client(test_db):
    app = FastAPI()
    app.include_router(reviews_api.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def scene_with_clip(test_db, tmp_path):
    """A project/video/scene whose vertical_video_url points at a real clip."""
    async def _make():
        clip = tmp_path / "clip.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error",
             "-f", "lavfi", "-i", "testsrc=duration=2:size=320x568:rate=10",
             "-pix_fmt", "yuv420p", str(clip)],
            check=True)
        proj = await crud.create_project(name="Review Sheets")
        video = await crud.create_video(project_id=proj["id"], title="V",
                                        orientation="VERTICAL")
        scene = await crud.create_scene(video_id=video["id"], display_order=0,
                                        prompt="a cat walks in the rain")
        scene = await crud.update_scene(
            scene["id"],
            vertical_video_url=f"file://{clip}",
            vertical_image_media_id="11111111-2222-3333-4444-555555555555")
        return proj, video, scene, clip
    return _make


async def test_prepare_review_sheets_builds_persisted_sheets(
        scene_with_clip, tmp_path):
    proj, video, scene, clip = await scene_with_clip()
    out = tmp_path / "sheets"

    info = await prepare_review_sheets(scene, [], "light", "VERTICAL", out)

    assert info["scene_id"] == scene["id"]
    assert info["n_frames"] > 0
    assert info["fps"] == 4.0
    assert info["sheets"], "expected at least one contact sheet"
    for s in info["sheets"]:
        assert Path(s).exists(), f"sheet must persist on disk: {s}"
        assert str(out) in s
    assert "SCORING DIMENSIONS" in info["prompt"]
    assert "a cat walks in the rain" in info["prompt"]


async def test_prepare_review_sheets_no_video_raises(test_db):
    proj = await crud.create_project(name="No Clip")
    video = await crud.create_video(project_id=proj["id"], title="V",
                                    orientation="VERTICAL")
    scene = await crud.create_scene(video_id=video["id"], display_order=0,
                                    prompt="x")
    with pytest.raises(ValueError):
        await prepare_review_sheets(scene, [], "light", "VERTICAL", Path("/tmp/x"))


def test_score_review_answer_applies_critical_cap():
    sr = score_review_answer(
        "s1",
        {"dimensions": {"character_consistency": 9.0, "prompt_adherence": 8.0,
                        "motion_quality": 8.0, "visual_fidelity": 8.0,
                        "temporal_coherence": 8.0, "composition": 8.0},
         "errors": [{"severity": "CRITICAL", "time_range": "3s-5s",
                     "description": "character morphs, extra limb"}],
         "usable_segments": [{"time_range": "0s-2s", "score": 8.0}]},
        n_frames=32, fps=4.0,
    )
    assert sr.scene_id == "s1"
    assert sr.has_critical_errors is True
    assert sr.dimensions.character_consistency == 3.0  # capped
    assert sr.overall_score <= 5.9  # forced below acceptable
    assert sr.verdict in ("poor", "unusable")
    assert sr.frames_analyzed == 32


def test_score_review_answer_rejects_missing_dimensions():
    with pytest.raises(RuntimeError):
        score_review_answer("s1", {"dimensions": {}, "errors": []},
                            n_frames=8, fps=4.0)


def test_score_review_answer_rejects_bad_severity():
    with pytest.raises(RuntimeError):
        score_review_answer(
            "s1",
            {"dimensions": {"character_consistency": 5.0, "prompt_adherence": 5.0,
                            "motion_quality": 5.0, "visual_fidelity": 5.0,
                            "temporal_coherence": 5.0, "composition": 5.0},
             "errors": [{"severity": "MEH", "time_range": "1s-2s",
                         "description": "x"}]},
            n_frames=8, fps=4.0)


async def test_review_sheets_then_submit_end_to_end(
        reviews_client, scene_with_clip):
    proj, video, scene, clip = await scene_with_clip()

    r = reviews_client.post(
        f"/api/videos/{video['id']}/review-sheets",
        json={"project_id": proj["id"], "mode": "light"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["sheets"]) == 1
    sheet = body["sheets"][0]
    assert sheet["scene_id"] == scene["id"]
    assert Path(sheet["sheets"][0]).exists()

    # The agent scores the sheets by hand and submits.
    r = reviews_client.post(
        f"/api/videos/{video['id']}/review-submit",
        json={"project_id": proj["id"], "mode": "light", "scores": [{
            "scene_id": scene["id"],
            "dimensions": {"character_consistency": 4.0, "prompt_adherence": 7.0,
                           "motion_quality": 6.0, "visual_fidelity": 7.0,
                           "temporal_coherence": 6.0, "composition": 7.0},
            "errors": [{"severity": "HIGH", "time_range": "1s-2s",
                        "description": "camera drifts left suddenly"}],
            "usable_segments": [{"time_range": "0s-1s", "score": 7.0}],
            "n_frames": sheet["n_frames"], "fps": sheet["fps"],
        }]})
    assert r.status_code == 200, r.text
    review = r.json()
    assert review["scenes_reviewed"] == 1
    sr = review["scene_reviews"][0]
    assert sr["has_critical_errors"] is False
    assert sr["overall_score"] > 0

    # review-regenerate with hand scores enqueues a bounded regen.
    r = reviews_client.post(
        f"/api/videos/{video['id']}/review-regenerate",
        json={"project_id": proj["id"], "mode": "light",
              "max_regenerations": 1, "bad_verdicts": ["poor", "unusable"],
              "scores": [{
                  "scene_id": scene["id"],
                  "dimensions": {"character_consistency": 2.0,
                                 "prompt_adherence": 2.0, "motion_quality": 2.0,
                                 "visual_fidelity": 2.0, "temporal_coherence": 2.0,
                                 "composition": 2.0},
                  "errors": [], "usable_segments": [],
                  "n_frames": 8, "fps": 4.0,
              }]})
    assert r.status_code == 200, r.text
    decisions = r.json()["decisions"]
    assert len(decisions) == 1
    assert decisions[0]["regenerated"] is True
    assert decisions[0]["request_id"]
