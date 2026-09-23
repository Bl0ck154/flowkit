"""Persistent lease for ad-hoc Flow API work.

Direct callers that do not own a durable Flow project share one project while
there is recent activity. The lease survives agent restarts and rotates after
the configured idle interval.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from agent.config import BASE_DIR, FLOW_SESSION_PROJECT_IDLE_S

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_STATE_PATH = Path(
    os.environ.get(
        "FLOW_SESSION_PROJECT_STATE",
        str(BASE_DIR / "flow_session_project.json"),
    )
)
_lock = asyncio.Lock()


def _read_state() -> dict:
    try:
        value = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _write_state(state: dict) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STATE_PATH.with_suffix(_STATE_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, _STATE_PATH)


def current_session_project() -> dict:
    state = _read_state()
    pid = str(state.get("project_id") or "")
    last = float(state.get("last_activity_at") or 0)
    age = max(0.0, time.time() - last) if last else None
    active = bool(_UUID_RE.fullmatch(pid)) and age is not None and age <= FLOW_SESSION_PROJECT_IDLE_S
    return {
        "project_id": pid if _UUID_RE.fullmatch(pid) else None,
        "title": state.get("title"),
        "last_activity_at": last or None,
        "idle_age_s": round(age, 3) if age is not None else None,
        "idle_limit_s": FLOW_SESSION_PROJECT_IDLE_S,
        "active": active,
    }


def touch_session_project(project_id: str) -> None:
    state = _read_state()
    if state.get("project_id") != project_id:
        return
    state["last_activity_at"] = time.time()
    _write_state(state)


async def ensure_session_project(client, *, title: str | None = None, force_new: bool = False) -> dict:
    async with _lock:
        state = current_session_project()
        if not force_new and state.get("active") and state.get("project_id"):
            touch_session_project(state["project_id"])
            return current_session_project()

        if not title:
            title = "FlowKit session " + datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
        result = await client.create_project(title)
        if result.get("error"):
            raise RuntimeError(result["error"])
        data = result.get("data") or {}
        pid = str(data.get("projectId") or "")
        if not _UUID_RE.fullmatch(pid):
            raise RuntimeError("Flow did not return a valid project id")
        state = {
            "project_id": pid,
            "title": str(data.get("title") or title),
            "created_at": time.time(),
            "last_activity_at": time.time(),
        }
        _write_state(state)
        return current_session_project()
