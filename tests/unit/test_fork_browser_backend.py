"""Check preservation of fork native-UI routing after upstream merges."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent import config
from agent.api import flow as flow_api
from agent.services import flow_batch as fb
from agent.services.flow_client import FlowClient


@pytest.mark.asyncio
async def test_default_extension_backend_uses_upstream_transport(monkeypatch):
    monkeypatch.setattr(config, "FLOW_BROWSER_BACKEND", "extension")
    client = FlowClient()
    client._send = AsyncMock(return_value={"status": 200, "data": "batch-result"})

    result = await client.batch_rpc(fb.RPC_GEN_IMAGE, "mock-freq", fb.CAPTCHA_IMAGE)

    assert result["status"] == 200
    client._send.assert_awaited_once()
    assert client._send.await_args.args[0] == "batch_rpc"


@pytest.mark.asyncio
async def test_opt_in_ui_generation_uses_native_playwright(monkeypatch):
    monkeypatch.setattr(config, "FLOW_BROWSER_BACKEND", "playwright_ui")
    client = FlowClient()
    client._batch_active_project = "project-1"
    client._send = AsyncMock(side_effect=AssertionError("extension must not submit UI generation"))
    with patch(
        "agent.services.flow_playwright_generation.run_flow_playwright_generation",
        new_callable=AsyncMock,
    ) as run_ui:
        run_ui.return_value = {"status": 200, "data": "real-ui-result"}
        result = await client.batch_rpc(fb.RPC_GEN_VIDEO, "mock-freq", fb.CAPTCHA_VIDEO)

    assert result["data"] == "real-ui-result"
    run_ui.assert_awaited_once_with(
        fb.RPC_GEN_VIDEO, "mock-freq", project_id="project-1", timeout=300,
    )
    client._send.assert_not_awaited()


@pytest.mark.asyncio
async def test_opt_in_ui_non_generation_uses_signed_cdp(monkeypatch):
    monkeypatch.setattr(config, "FLOW_BROWSER_BACKEND", "playwright_ui")
    client = FlowClient()
    client._batch_active_project = "project-1"
    client._send = AsyncMock(side_effect=AssertionError("metadata must go through CDP"))
    with patch(
        "agent.services.browser_session.run_flow_batch_rpc", new_callable=AsyncMock
    ) as cdp:
        cdp.return_value = {"status": 200, "data": "cdp-result"}
        result = await client.batch_rpc(fb.RPC_MEDIA, "freq", match="video")

    assert result["data"] == "cdp-result"
    cdp.assert_awaited_once_with(
        fb.RPC_MEDIA, "freq", captcha_action=None, match="video",
        project_id="project-1", timeout=300,
    )


@pytest.mark.asyncio
async def test_ui_backend_upscale_uses_cdp_not_composer(monkeypatch):
    monkeypatch.setattr(config, "FLOW_BROWSER_BACKEND", "playwright_ui")
    client = FlowClient()
    with (
        patch("agent.services.browser_session.run_flow_batch_rpc",
              new_callable=AsyncMock) as cdp,
        patch("agent.services.flow_playwright_generation.run_flow_playwright_generation",
              new_callable=AsyncMock) as ui,
    ):
        cdp.return_value = {"status": 200}
        result = await client.batch_rpc(fb.RPC_UPSCALE, "freq", fb.CAPTCHA_VIDEO)
    assert result["status"] == 200
    cdp.assert_awaited_once()
    ui.assert_not_awaited()


@pytest.mark.asyncio
async def test_ui_backend_custom_streamchat_uses_extension_bridge(monkeypatch):
    monkeypatch.setattr(config, "FLOW_BROWSER_BACKEND", "playwright_ui")
    client = FlowClient()
    client._send = AsyncMock(return_value={"status": 200})
    with patch("agent.services.browser_session.run_flow_batch_rpc",
               new_callable=AsyncMock) as cdp:
        result = await client.batch_rpc(
            "StreamChat", "freq", custom_path="/custom-path",
        )
    assert result["status"] == 200
    client._send.assert_awaited_once()
    cdp.assert_not_awaited()


@pytest.mark.asyncio
async def test_ui_backend_respects_existing_account_hold(monkeypatch):
    monkeypatch.setattr(config, "FLOW_BROWSER_BACKEND", "playwright_ui")
    client = FlowClient()
    client._generation_unusual_until = time.monotonic() + 3600
    with patch("agent.services.flow_playwright_generation.run_flow_playwright_generation",
               new_callable=AsyncMock) as ui:
        result = await client.batch_rpc(fb.RPC_GEN_IMAGE, "freq", fb.CAPTCHA_IMAGE)
    assert result["status"] == 429
    ui.assert_not_awaited()


@pytest.mark.asyncio
async def test_ui_upload_restores_fresh_picker_cache(monkeypatch):
    monkeypatch.setattr(config, "FLOW_BROWSER_BACKEND", "playwright_ui")
    client = MagicMock()
    client.upload_image = AsyncMock(return_value={
        "status": 200, "_mediaId": "media-1", "data": {"media": {"name": "media-1"}},
    })
    with (
        patch.object(flow_api, "_resolve_direct_project", new_callable=AsyncMock,
                     return_value="project-1"),
        patch("agent.services.flow_ui_generation.cache_uploaded_media_bytes",
              return_value=None) as cache,
        patch("agent.services.flow_ui_generation.mark_uploaded_media_for_ui_refresh") as refresh,
    ):
        result = await flow_api._upload_image_bytes(
            client, b"image-bytes", project_id="project-1",
            mime_type="image/png", file_name="reference.png",
        )
    assert result["media_id"] == "media-1"
    cache.assert_called_once_with(
        "media-1", b"image-bytes",
        mime_type="image/png", file_name="reference.png",
    )
    refresh.assert_called_once_with("project-1", "media-1")


@pytest.mark.asyncio
async def test_extension_upload_does_not_touch_local_browser_cache(monkeypatch):
    monkeypatch.setattr(config, "FLOW_BROWSER_BACKEND", "extension")
    client = MagicMock()
    client.upload_image = AsyncMock(return_value={
        "status": 200, "_mediaId": "media-1", "data": {},
    })
    with (
        patch.object(flow_api, "_resolve_direct_project", new_callable=AsyncMock,
                     return_value="project-1"),
        patch("agent.services.flow_ui_generation.cache_uploaded_media_bytes") as cache,
    ):
        await flow_api._upload_image_bytes(
            client, b"image-bytes", project_id="project-1",
            mime_type="image/png", file_name="reference.png",
        )
    cache.assert_not_called()
