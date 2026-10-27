"""Exercise routes whose module-level imports were lost during upstream merge."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.api import flow


@pytest.mark.asyncio
async def test_browser_status_checks_real_session_inspector():
    client = MagicMock(connected=True, _flow_key=None)
    client.generation_guard_status = {"cooldown_reason": None}
    with (
        patch.object(flow, "get_flow_client", return_value=client),
        patch.object(flow, "inspect_flow_session", new_callable=AsyncMock) as inspect,
    ):
        inspect.return_value = {
            "signedIn": True, "flowTabPresent": True,
            "atTokenPresent": True, "url": "https://flow.google.com/",
        }
        result = await flow.extension_status()
    assert result["authenticated"] is True
    assert result["transport"] == "batch"
    inspect.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_ensure_session_calls_local_flow_browser_recovery():
    client = MagicMock(connected=True)
    with (
        patch.object(flow, "get_flow_client", return_value=client),
        patch.object(flow, "ensure_flow_session", new_callable=AsyncMock) as recover,
    ):
        recover.return_value = {"signedIn": True, "state": "AUTHENTICATED"}
        result = await flow.ensure_session()
    assert result["authenticated"] is True
    recover.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_account_route_calls_local_inspector():
    client = MagicMock(connected=True)
    with (
        patch.object(flow, "get_flow_client", return_value=client),
        patch.object(flow, "inspect_google_account", new_callable=AsyncMock) as inspect,
    ):
        inspect.return_value = {"account": "test-account"}
        result = await flow.get_account()
    assert result == {"account": "test-account"}
    inspect.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_capabilities_route_uses_dynamic_model_inspector():
    with patch.object(flow, "image_capabilities", new_callable=AsyncMock) as inspect:
        inspect.return_value = {"models": ["BELUGA"]}
        result = await flow.get_image_capabilities(refresh=True)
    assert result["models"] == ["BELUGA"]
    inspect.assert_awaited_once_with(refresh=True)
