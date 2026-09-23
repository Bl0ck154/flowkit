import time

import pytest

from agent.services import flow_project_session as fps

PROJECT_A = "11111111-2222-3333-4444-555555555555"
PROJECT_B = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class FakeClient:
    def __init__(self):
        self.created = []

    async def create_project(self, title):
        self.created.append(title)
        pid = PROJECT_A if len(self.created) == 1 else PROJECT_B
        return {"status": 200, "data": {"projectId": pid, "title": title}}


@pytest.mark.asyncio
async def test_session_project_reuses_inside_idle_window(tmp_path, monkeypatch):
    monkeypatch.setattr(fps, "_STATE_PATH", tmp_path / "lease.json")
    monkeypatch.setattr(fps, "FLOW_SESSION_PROJECT_IDLE_S", 7200.0)
    client = FakeClient()

    first = await fps.ensure_session_project(client, title="Session A")
    second = await fps.ensure_session_project(client, title="Ignored")

    assert first["project_id"] == PROJECT_A
    assert second["project_id"] == PROJECT_A
    assert len(client.created) == 1


@pytest.mark.asyncio
async def test_session_project_rotates_after_idle(tmp_path, monkeypatch):
    monkeypatch.setattr(fps, "_STATE_PATH", tmp_path / "lease.json")
    monkeypatch.setattr(fps, "FLOW_SESSION_PROJECT_IDLE_S", 10.0)
    client = FakeClient()

    await fps.ensure_session_project(client, title="Session A")
    state = fps._read_state()
    state["last_activity_at"] = time.time() - 11
    fps._write_state(state)

    rotated = await fps.ensure_session_project(client, title="Session B")
    assert rotated["project_id"] == PROJECT_B
    assert len(client.created) == 2
