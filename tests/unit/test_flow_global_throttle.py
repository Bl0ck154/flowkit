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

    async def fake_send(method, params, timeout=300):
        nonlocal active, max_active
        assert method == "batch_rpc"
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {"status": 200, "data": "ok"}

    monkeypatch.setattr(client, "_send", fake_send)
    await asyncio.gather(
        client.batch_rpc("a", "x", captcha_action=fb.CAPTCHA_VIDEO),
        client.batch_rpc("b", "y", captcha_action=fb.CAPTCHA_IMAGE),
    )
    assert max_active == 1


@pytest.mark.asyncio
async def test_unusual_activity_opens_local_circuit_breaker(monkeypatch):
    monkeypatch.setattr(fc, "FLOW_GENERATION_MAX_CONCURRENT", 1)
    monkeypatch.setattr(fc, "FLOW_GENERATION_MIN_INTERVAL_S", 0.0)
    monkeypatch.setattr(fc, "FLOW_UNUSUAL_ACTIVITY_COOLDOWN_S", 120.0)
    client = fc.FlowClient()
    calls = 0

    async def fake_send(method, params, timeout=300):
        nonlocal calls
        calls += 1
        return {
            "status": 200,
            "data": "PUBLIC_ERROR_UNUSUAL_ACTIVITY reCAPTCHA evaluation failed",
        }

    monkeypatch.setattr(client, "_send", fake_send)
    first = await client.batch_rpc("a", "x", captcha_action=fb.CAPTCHA_VIDEO)
    second = await client.batch_rpc("b", "y", captcha_action=fb.CAPTCHA_VIDEO)

    assert first["status"] == 200
    assert second["status"] == 429
    assert "local cooldown active" in second["error"]
    assert calls == 1
    assert client.generation_guard_status["cooldown_active"] is True
    assert client.generation_guard_status["last_unusual_activity_rpc"] == "a"


@pytest.mark.asyncio
async def test_non_generation_rpc_bypasses_generation_guard(monkeypatch):
    client = fc.FlowClient()
    client._generation_unusual_until = asyncio.get_running_loop().time() + 60
    calls = 0

    async def fake_send(method, params, timeout=300):
        nonlocal calls
        calls += 1
        return {"status": 200, "data": "metadata"}

    monkeypatch.setattr(client, "_send", fake_send)
    result = await client.batch_rpc("meta", "x")
    assert result["status"] == 200
    assert calls == 1
