"""Tests for review provider-neutrality and bounded auto-regeneration.

pytest-asyncio runs in AUTO mode (see pytest.ini).
"""
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api import reviews as reviews_api
from agent.db import crud
from agent.models.review import (
    DimensionScores,
    SceneReview,
    VideoReview,
)
from agent.services.video_reviewer import _local_media_path


@pytest.fixture
def reviews_client(test_db, monkeypatch):
    app = FastAPI()
    app.include_router(reviews_api.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=False)


def _dims():
    return DimensionScores(character_consistency=1, prompt_adherence=1,
                           motion_quality=1, visual_fidelity=1,
                           temporal_coherence=1, composition=1)


def _scene_review(sid, verdict, critical=False):
    return SceneReview(scene_id=sid, overall_score=1.0, verdict=verdict,
                       dimensions=_dims(), errors=[], usable_segments=[],
                       fix_guide="", frames_analyzed=4, fps_used=4.0,
                       has_critical_errors=critical)


def _video_review(vid, scene_reviews):
    return VideoReview(video_id=vid, project_id="p", mode="light",
                       orientation="VERTICAL", overall_score=1.0,
                       verdict="poor", scene_reviews=scene_reviews,
                       scenes_reviewed=len(scene_reviews), scenes_skipped=0)


async def _mk_scene(test_db, tmp_path, vid, order, image_media_id="img-mid"):
    scene = await crud.create_scene(video_id=vid, display_order=order,
                                    prompt=f"scene {order}")
    clip = tmp_path / f"rev_{order}.mp4"
    clip.write_bytes(b"fake")
    await crud.update_scene(scene["id"], vertical_video_url=f"file://{clip}",
                            vertical_image_media_id=image_media_id)
    return scene


async def test_local_media_path_file_url(tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x")
    assert _local_media_path(f"file://{f}") == f
    assert _local_media_path(str(f)) == f
    assert _local_media_path("https://example.com/a.mp4") is None
    assert _local_media_path("") is None
    assert _local_media_path(None) is None
    assert _local_media_path(f"file://{tmp_path}/missing.mp4") is None


async def test_review_regenerate_enqueues_bad_scenes(reviews_client, test_db,
                                                     tmp_path, monkeypatch):
    proj = await crud.create_project(name="Rev Test")
    video = await crud.create_video(project_id=proj["id"], title="V",
                                    orientation="VERTICAL")
    s_bad = await _mk_scene(test_db, tmp_path, video["id"], 0)
    s_good = await _mk_scene(test_db, tmp_path, video["id"], 1)

    async def fake_review(*a, **k):
        return _video_review(video["id"],
                             [_scene_review(s_bad["id"], "poor"),
                              _scene_review(s_good["id"], "good")])

    monkeypatch.setattr(reviews_api, "review_video", fake_review)

    r = reviews_client.post(
        f"/api/videos/{video['id']}/review-regenerate",
        json={"project_id": proj["id"], "max_regenerations": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    decisions = {d["scene_id"]: d for d in body["decisions"]}
    assert decisions[s_bad["id"]]["regenerated"] is True
    assert decisions[s_bad["id"]]["request_id"]
    assert decisions[s_good["id"]]["regenerated"] is False

    reqs = await crud.list_requests(scene_id=s_bad["id"])
    assert any(x["type"] == "REGENERATE_VIDEO" for x in reqs)


async def test_review_regenerate_bound_reached(reviews_client, test_db,
                                               tmp_path, monkeypatch):
    proj = await crud.create_project(name="Rev Bound")
    video = await crud.create_video(project_id=proj["id"], title="V",
                                    orientation="VERTICAL")
    s_bad = await _mk_scene(test_db, tmp_path, video["id"], 0)

    async def fake_review(*a, **k):
        return _video_review(video["id"], [_scene_review(s_bad["id"], "unusable")])

    monkeypatch.setattr(reviews_api, "review_video", fake_review)

    body_json = {"project_id": proj["id"], "max_regenerations": 1}
    r1 = reviews_client.post(f"/api/videos/{video['id']}/review-regenerate",
                             json=body_json)
    assert r1.json()["decisions"][0]["regenerated"] is True

    # Second run: bound reached, no new request.
    r2 = reviews_client.post(f"/api/videos/{video['id']}/review-regenerate",
                             json=body_json)
    assert r2.status_code == 200
    d = r2.json()["decisions"][0]
    assert d["regenerated"] is False
    assert "bound reached" in d["reason"]

    reqs = await crud.list_requests(scene_id=s_bad["id"])
    assert sum(1 for x in reqs if x["type"] == "REGENERATE_VIDEO") == 1


async def test_review_regenerate_no_image_skips(reviews_client, test_db,
                                                tmp_path, monkeypatch):
    proj = await crud.create_project(name="Rev NoImg")
    video = await crud.create_video(project_id=proj["id"], title="V",
                                    orientation="VERTICAL")
    scene = await crud.create_scene(video_id=video["id"], display_order=0,
                                    prompt="x")
    # no vertical_image_media_id set

    async def fake_review(*a, **k):
        return _video_review(video["id"], [_scene_review(scene["id"], "poor")])

    monkeypatch.setattr(reviews_api, "review_video", fake_review)

    r = reviews_client.post(
        f"/api/videos/{video['id']}/review-regenerate",
        json={"project_id": proj["id"]})
    assert r.status_code == 200, r.text
    d = r.json()["decisions"][0]
    assert d["regenerated"] is False
    assert "no scene image" in d["reason"]


async def test_review_regenerate_404(reviews_client, test_db):
    r = reviews_client.post("/api/videos/nope/review-regenerate",
                            json={"project_id": "x"})
    assert r.status_code == 404
