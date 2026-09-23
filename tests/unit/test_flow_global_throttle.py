import asyncio

import pytest

from agent.services import flow_batch as fb
from agent.services import flow_client as fc


@pytest.mark.asyncio
async def test_generation_rpc_is_globally_serialized(monkeypatch):
    monkeypatch.setattr(fc, "FLOW_GENERATION_MAX_CONCURRENT", 1)
    monkeypatch.setattr(fc, "FLOW_GENERATION_MIN_INTERVAL_S", 0.0)
    client = fc.FlowClient()
    active = 0
    max_active = 0

    async def fake_run(*args, **kwargs):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {"status": 200, "data": "ok"}

    monkeypatch.setattr(fc, "run_flow_ui_generation", fake_run)
    await asyncio.gather(
        client.batch_rpc(fb.RPC_GEN_VIDEO_TEXT, "x", captcha_action=fb.CAPTCHA_VIDEO),
        client.batch_rpc(fb.RPC_GEN_IMAGE, "y", captcha_action=fb.CAPTCHA_IMAGE),
    )
    assert max_active == 1


@pytest.mark.asyncio
async def test_unusual_activity_opens_local_circuit_breaker(monkeypatch):
    monkeypatch.setattr(fc, "FLOW_GENERATION_MAX_CONCURRENT", 1)
    monkeypatch.setattr(fc, "FLOW_GENERATION_MIN_INTERVAL_S", 0.0)
    monkeypatch.setattr(fc, "FLOW_UNUSUAL_ACTIVITY_COOLDOWN_S", 120.0)
    client = fc.FlowClient()
    calls = 0

    async def fake_run(*args, **kwargs):
        nonlocal calls
        calls += 1
        return {"status": 200, "data": "PUBLIC_ERROR_UNUSUAL_ACTIVITY reCAPTCHA evaluation failed"}

    monkeypatch.setattr(fc, "run_flow_ui_generation", fake_run)
    first = await client.batch_rpc(fb.RPC_GEN_VIDEO_TEXT, "x", captcha_action=fb.CAPTCHA_VIDEO)
    second = await client.batch_rpc(fb.RPC_GEN_VIDEO_TEXT, "y", captcha_action=fb.CAPTCHA_VIDEO)

    assert first["status"] == 200
    assert second["status"] == 429
    assert "local cooldown active" in second["error"]
    assert calls == 1


@pytest.mark.asyncio
async def test_upload_with_image_captcha_stays_on_direct_batch_transport(monkeypatch):
    client = fc.FlowClient()
    direct_calls = []
    ui_calls = []

    async def fake_direct(*args, **kwargs):
        direct_calls.append((args, kwargs))
        return {"status": 200, "data": "uploaded"}

    async def fake_ui(*args, **kwargs):
        ui_calls.append((args, kwargs))
        return {"status": 200, "data": "wrong transport"}

    monkeypatch.setattr(fc, "run_flow_batch_rpc", fake_direct)
    monkeypatch.setattr(fc, "run_flow_ui_generation", fake_ui)

    result = await client.batch_rpc(
        fb.RPC_UPLOAD_IMAGE,
        "upload-envelope",
        captcha_action=fb.CAPTCHA_IMAGE,
    )

    assert result["data"] == "uploaded"
    assert len(direct_calls) == 1
    assert ui_calls == []
