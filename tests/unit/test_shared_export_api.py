"""Fork export endpoints share the current upstream PR #40 poller."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from agent.api import flow, upscale_status
from agent.services.flow_poll import check_workflow_status


@pytest.mark.asyncio
async def test_export_allocates_session_project_for_projectless_calls():
    client = MagicMock(connected=True)
    client.upscale_video = AsyncMock(return_value={
        "status": 200, "data": {
            "workflows": [{"name": "upscaled-media", "primary_media_id": "upscaled-media"}],
        },
    })
    with (
        patch.object(upscale_status, "get_flow_client", return_value=client),
        patch.object(upscale_status, "ensure_session_project",
                     new_callable=AsyncMock) as lease,
    ):
        lease.return_value = {"project_id": "project-123"}
        result = await upscale_status.export_video(
            upscale_status.ExportVideoRequest(media_id="video")
        )

    lease.assert_awaited_once_with(client)
    client.upscale_video.assert_awaited_once_with(
        media_id="video", scene_id="export",
        aspect_ratio="VIDEO_ASPECT_RATIO_LANDSCAPE",
        resolution="VIDEO_RESOLUTION_1080P",
        project_id="project-123",
    )
    assert result["flowkitPolling"]["mode"] == "media_redirect"
    assert result["flowkitPolling"]["project_id"] == "project-123"
    assert result["export"]["next"] == "/api/flow/check-status"
    assert result["export"]["check_status_mode"] == "export"


@pytest.mark.asyncio
async def test_export_with_explicit_project_avoids_session_allocation():
    client = MagicMock(connected=True)
    client.upscale_video = AsyncMock(return_value={"status": 200, "data": {"workflows": []}})
    with (
        patch.object(upscale_status, "get_flow_client", return_value=client),
        patch.object(upscale_status, "ensure_session_project",
                     new_callable=AsyncMock) as lease,
    ):
        await upscale_status.export_video(
            upscale_status.ExportVideoRequest(media_id="video", project_id="existing-project")
        )
    lease.assert_not_awaited()
    assert client.upscale_video.await_args.kwargs["project_id"] == "existing-project"


@pytest.mark.asyncio
async def test_export_project_lease_failure_is_a_clean_http_error():
    client = MagicMock(connected=True)
    with (
        patch.object(upscale_status, "get_flow_client", return_value=client),
        patch.object(upscale_status, "ensure_session_project",
                     new_callable=AsyncMock, side_effect=RuntimeError("cannot create")),
    ):
        with pytest.raises(HTTPException) as error:
            await upscale_status.export_video(
                upscale_status.ExportVideoRequest(media_id="video")
            )
    assert error.value.status_code == 502


@pytest.mark.asyncio
async def test_shared_check_status_export_sets_download_ready():
    client = MagicMock(connected=True)
    client.resolve_media_url = AsyncMock(return_value={
        "status": 200,
        "data": {"url": "https://flow-content.google/video/export.mp4?sig=x",
                 "contentType": "video/mp4"},
    })
    with patch.object(flow, "get_flow_client", return_value=client):
        result = await flow.check_status(flow.CheckStatusRequest(
            mode="export", project_id="project-123",
            workflows=[{"name": "workflow-1", "primary_media_id": "video-upscaled"}],
        ))
    assert result["download_ready"] is True
    assert result["workflows"][0]["media"]["resolved_via"] == "as29s"
    client.resolve_media_url.assert_awaited_once_with("video-upscaled")


@pytest.mark.asyncio
async def test_legacy_export_status_alias_still_uses_shared_poll():
    client = MagicMock(connected=True)
    client.resolve_media_url = AsyncMock(return_value={
        "status": 404, "error": "not ready",
    })
    with patch.object(upscale_status, "get_flow_client", return_value=client):
        result = await upscale_status.check_export_status(
            upscale_status.CheckExportStatusRequest(
                workflows=[{"name": "workflow-1", "primary_media_id": "video-upscaled"}],
            )
        )
    assert result["download_ready"] is False
    assert result["workflows"][0]["status"] == "PENDING"


@pytest.mark.asyncio
async def test_shared_poller_rejects_image_url_as_finished_video():
    client = MagicMock()
    client.resolve_media_url = AsyncMock(return_value={
        "status": 200,
        "data": {"url": "https://flow-content.google/image/not-video.jpg?sig=x",
                 "contentType": "image/jpeg"},
    })
    result = await check_workflow_status(
        [{"name": "wf", "primary_media_id": "video-upscaled"}],
        mode="media_redirect", client=client,
    )
    assert result["done"] is False
    assert result["status"] == "PENDING"


@pytest.mark.asyncio
async def test_export_provider_error_preserves_http_status():
    client = MagicMock(connected=True)
    client.upscale_video = AsyncMock(return_value={"status": 403, "error": "plan restricted"})
    with patch.object(upscale_status, "get_flow_client", return_value=client):
        with pytest.raises(HTTPException) as error:
            await upscale_status.export_video(
                upscale_status.ExportVideoRequest(media_id="video", project_id="project-123")
            )
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_export_requires_browser_connection():
    with patch.object(upscale_status, "get_flow_client", return_value=MagicMock(connected=False)):
        with pytest.raises(HTTPException) as error:
            await upscale_status.export_video(
                upscale_status.ExportVideoRequest(media_id="video")
            )
    assert error.value.status_code == 503
