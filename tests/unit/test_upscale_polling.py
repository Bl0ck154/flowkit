"""Tests for active headless Flow upscale polling."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.services.upscale_polling import (
    _fetch_media_url,
    annotate_upscale_polling,
    check_upscale_status,
    extract_upscale_workflows,
)


def _upscale_submit():
    return {
        "status": 200,
        "data": {
            "operations": [
                {
                    "operation": {"name": "legacy-op"},
                    "status": "MEDIA_GENERATION_STATUS_PENDING",
                }
            ],
            "workflows": [
                {
                    "name": "upscale-workflow-1",
                    "metadata": {
                        "primaryMediaId": "123e4567-e89b-12d3-a456-426614174000_upsampled"
                    },
                }
            ],
            "media": [
                {
                    "name": "123e4567-e89b-12d3-a456-426614174000_upsampled",
                    "video": {"generatedVideo": {"model": "veo_3_1_upsampler_1080p"}},
                }
            ],
        },
    }


def test_extract_upscale_workflow_preserves_logical_upsampled_media_id():
    assert extract_upscale_workflows(_upscale_submit()) == [
        {
            "name": "upscale-workflow-1",
            "primary_media_id": "123e4567-e89b-12d3-a456-426614174000_upsampled",
        }
    ]


def test_annotate_upscale_submit_adds_media_redirect_polling_descriptor():
    result = _upscale_submit()
    annotate_upscale_polling(result)

    assert result["data"]["flowkitPolling"] == {
        "mode": "media_redirect",
        "workflows": [
            {
                "name": "upscale-workflow-1",
                "primary_media_id": "123e4567-e89b-12d3-a456-426614174000_upsampled",
            }
        ],
    }


@pytest.mark.asyncio
async def test_upscale_redirect_probe_uses_logical_upsampled_media_id():
    client = MagicMock()
    client._send = AsyncMock(return_value={"status": 200, "data": {}})

    await _fetch_media_url(
        client,
        "123e4567-e89b-12d3-a456-426614174000_upsampled",
    )

    client._send.assert_awaited_once_with(
        "trpc_request",
        {
            "url": (
                "https://labs.google/fx/api/trpc/media.getMediaUrlRedirect"
                "?name=123e4567-e89b-12d3-a456-426614174000_upsampled"
            ),
            "method": "GET",
            "headers": {"content-type": "application/json"},
            "responseMode": "url",
        },
        timeout=15,
    )


@pytest.mark.asyncio
async def test_upscale_poll_is_pending_until_redirect_resolves_to_media():
    logical_id = "123e4567-e89b-12d3-a456-426614174000_upsampled"
    client = MagicMock()
    client._send = AsyncMock(
        return_value={
            "status": 200,
            "data": {
                "url": (
                    "https://labs.google/fx/api/trpc/media.getMediaUrlRedirect"
                    f"?name={logical_id}"
                ),
                "contentType": "application/json",
            },
        }
    )

    with patch(
        "agent.services.upscale_polling.get_flow_client",
        return_value=client,
    ):
        result = await check_upscale_status(
            [
                {
                    "name": "upscale-workflow-1",
                    "primary_media_id": logical_id,
                }
            ]
        )

    assert result["done"] is False
    assert result["status"] == "PENDING"
    item = result["workflows"][0]
    assert item["status"] == "PENDING"
    assert item["probe"]["diagnostic"] == "media redirect not ready"


@pytest.mark.asyncio
async def test_upscale_poll_completes_when_signed_media_redirect_is_available():
    logical_id = "123e4567-e89b-12d3-a456-426614174000_upsampled"
    signed_url = (
        "https://flow-content.google/video/"
        "7a0d9f41-9d6f-42a8-93be-d759f31d52fb?Signature=test"
    )
    client = MagicMock()
    client._send = AsyncMock(
        return_value={
            "status": 200,
            "data": {
                "url": signed_url,
                "contentType": "video/mp4",
            },
        }
    )
    client.get_media = AsyncMock(side_effect=AssertionError("legacy get_media forbidden"))
    client.check_video_status = AsyncMock(
        side_effect=AssertionError("legacy operation poll forbidden")
    )

    with patch(
        "agent.services.upscale_polling.get_flow_client",
        return_value=client,
    ):
        result = await check_upscale_status(
            [
                {
                    "name": "upscale-workflow-1",
                    "metadata": {"primaryMediaId": logical_id},
                }
            ]
        )

    client.get_media.assert_not_awaited()
    client.check_video_status.assert_not_awaited()
    assert result["done"] is True
    assert result["status"] == "COMPLETED"

    item = result["workflows"][0]
    assert item["status"] == "MEDIA_GENERATION_STATUS_SUCCESSFUL"
    assert item["media"]["media_id"] == logical_id
    assert item["media"]["url"] == signed_url
    assert item["media"]["content_type"] == "video/mp4"
    assert item["media"]["resolved_via"] == "media.getMediaUrlRedirect"


@pytest.mark.asyncio
async def test_upscale_poll_keeps_http_400_as_pending_probe_diagnostic():
    client = MagicMock()
    client._send = AsyncMock(
        return_value={
            "status": 400,
            "data": {"error": {"message": "not ready"}},
        }
    )

    with patch(
        "agent.services.upscale_polling.get_flow_client",
        return_value=client,
    ):
        result = await check_upscale_status(
            [
                {
                    "name": "upscale-workflow-1",
                    "primary_media_id": "media-upsampled",
                }
            ]
        )

    assert result["done"] is False
    assert result["workflows"][0]["probe"]["http_status"] == 400
    assert result["workflows"][0]["probe"]["diagnostic"] == "API_400"
