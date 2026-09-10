import asyncio
import pytest

from agent.services import browser_session as bs

PID = "11111111-2222-3333-4444-555555555555"


@pytest.mark.asyncio
async def test_batch_rpc_matches_flow_wiz_source_path_and_locale(monkeypatch):
    async def fake_targets():
        return [{
            "type": "page",
            "url": f"https://flow.google.com/project/{PID}",
            "webSocketDebuggerUrl": "ws://flow-test",
        }]

    captured = {}

    async def fake_evaluate(ws_url, expression, timeout=30):
        captured["ws_url"] = ws_url
        captured["expression"] = expression
        return {"status": 200, "text": "ok"}

    monkeypatch.setattr(bs, "_targets", fake_targets)
    monkeypatch.setattr(bs, "_evaluate", fake_evaluate)

    result = await bs.run_flow_batch_rpc(
        "ogiZ0b", "f.req payload", project_id=PID, captcha_action=None
    )

    assert result["status"] == 200
    expression = captured["expression"]
    assert "source-path=" in expression
    assert "location.pathname" in expression
    assert "document.documentElement.lang" in expression
    assert "hl=en-AU" not in expression
    assert "__flowkitCaptchaMintTail" in expression
    assert "releaseMint" in expression


def test_redundant_root_pruning_keeps_project_tabs():
    targets = [
        {"id": "root-a", "type": "page", "url": "https://flow.google.com/"},
        {"id": "root-b", "type": "page", "url": "https://flow.google.com/"},
        {"id": "project", "type": "page", "url": f"https://flow.google.com/project/{PID}"},
    ]
    assert bs._redundant_flow_root_ids(targets, "project") == ["root-a", "root-b"]
    assert bs._redundant_flow_root_ids(targets[:2], "root-a") == ["root-b"]
    assert bs._redundant_flow_root_ids(targets[:2]) == []


def test_flow_page_ids_ignore_iframes_workers_and_idle_page():
    targets = [
        {"id": "flow-root", "type": "page", "url": "https://flow.google.com/"},
        {"id": "flow-project", "type": "page", "url": f"https://flow.google.com/project/{PID}"},
        {"id": "legacy", "type": "page", "url": "https://labs.google/fx/tools/flow"},
        {"id": "iframe", "type": "iframe", "url": "https://flow.google.com/embed"},
        {"id": "worker", "type": "service_worker", "url": "https://flow.google.com/sw.js"},
        {"id": "idle", "type": "page", "url": "http://127.0.0.1:8100/health"},
    ]
    assert bs._flow_page_ids(targets) == ["flow-root", "flow-project", "legacy"]


@pytest.mark.asyncio
async def test_close_flow_tabs_only_closes_flow_pages(monkeypatch):
    async def fake_targets():
        return [
            {"id": "flow", "type": "page", "url": "https://flow.google.com/"},
            {"id": "idle", "type": "page", "url": "http://127.0.0.1:8100/health"},
            {"id": "iframe", "type": "iframe", "url": "https://flow.google.com/embed"},
        ]

    closed = []

    def fake_http_text(url, method="GET"):
        closed.append(url)
        return "ok"

    monkeypatch.setattr(bs, "_targets", fake_targets)
    monkeypatch.setattr(bs, "_http_text", fake_http_text)

    assert await bs.close_flow_tabs() == 1
    assert closed == [f"{bs.CDP_BASE}/json/close/flow"]


@pytest.mark.asyncio
async def test_ensure_session_parks_flow_after_idle_delay(monkeypatch):
    parked = asyncio.Event()

    async def fake_ensure(wait_s=3.0):
        return {"signedIn": True, "flowTabPresent": True}

    async def fake_close():
        parked.set()
        return 1

    monkeypatch.setattr(bs, "FLOW_TAB_IDLE_CLOSE_S", 0.001)
    monkeypatch.setattr(bs, "_ensure_flow_session_once", fake_ensure)
    monkeypatch.setattr(bs, "close_flow_tabs", fake_close)

    try:
        result = await bs.ensure_flow_session(wait_s=0)
        assert result["signedIn"] is True
        await asyncio.wait_for(parked.wait(), timeout=0.2)
    finally:
        bs._cancel_flow_tab_idle_close()
