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
    assert bs._redundant_flow_root_ids(targets[:2]) == []
