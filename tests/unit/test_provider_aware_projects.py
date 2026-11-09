"""Tests for provider-aware project creation and refresh-urls no-op.

pytest-asyncio runs in AUTO mode (see pytest.ini).
"""
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api import projects as projects_api
from agent.api import flow as flow_api
from agent.db import crud


@pytest.fixture
def projects_client(test_db, monkeypatch):
    app = FastAPI()
    app.include_router(projects_api.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def flow_client(test_db, monkeypatch):
    app = FastAPI()
    app.include_router(flow_api.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=False)


def _disconnected_client(monkeypatch, target_module):
    """Patch get_flow_client in target_module to return a disconnected client."""
    client = MagicMock()
    client.connected = False
    # flow_project_id validates UUID format like the real client
    client.flow_project_id = lambda req: (
        req if req and __import__("re").match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            req, __import__("re").I) else None)
    monkeypatch.setattr(target_module, "get_flow_client", lambda: client)
    return client


async def test_create_project_without_extension_local_only(
        projects_client, test_db, monkeypatch):
    _disconnected_client(monkeypatch, projects_api)

    r = projects_client.post("/api/projects", json={"name": "Local Only"})
    assert r.status_code == 200, r.text
    body = r.json()
    # minted UUID, not a Flow project
    uuid.UUID(body["id"])
    assert body["name"] == "Local Only"

    row = await crud.get_project(body["id"])
    assert row is not None


async def test_create_project_with_explicit_flow_id_no_extension(
        projects_client, test_db, monkeypatch):
    _disconnected_client(monkeypatch, projects_api)
    fid = str(uuid.uuid4())

    r = projects_client.post("/api/projects",
                             json={"name": "Reuse", "flow_project_id": fid})
    assert r.status_code == 200, r.text
    assert r.json()["id"] == fid


async def test_refresh_urls_noop_for_local_media(flow_client, test_db,
                                                 monkeypatch, tmp_path):
    _disconnected_client(monkeypatch, flow_api)

    proj = await crud.create_project(name="Local Media")
    video = await crud.create_video(project_id=proj["id"], title="V",
                                    orientation="VERTICAL")
    scene = await crud.create_scene(video_id=video["id"], display_order=0,
                                    prompt="x")
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"fake")
    await crud.update_scene(scene["id"], vertical_video_url=f"file://{clip}")

    # No extension connected AND all URLs local -> no-op, not 503.
    r = flow_client.post(f"/api/flow/refresh-urls/{proj['id']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["refreshed"] == 0
    assert "nothing to refresh" in body["skipped"]


async def test_refresh_urls_still_needs_extension_for_remote(
        flow_client, test_db, monkeypatch):
    _disconnected_client(monkeypatch, flow_api)

    proj = await crud.create_project(name="Remote Media")
    video = await crud.create_video(project_id=proj["id"], title="V",
                                    orientation="VERTICAL")
    scene = await crud.create_scene(video_id=video["id"], display_order=0,
                                    prompt="x")
    await crud.update_scene(
        scene["id"], vertical_video_url="https://example.com/clip.mp4")

    r = flow_client.post(f"/api/flow/refresh-urls/{proj['id']}")
    assert r.status_code == 503  # extension required for remote URLs
