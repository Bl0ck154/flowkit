"""Unit tests for Gemini Omni Flash Flow submissions and workflow polling."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.services.omni_flash import (
    OMNI_FLASH_MAX_REFERENCE_IMAGES,
    _load_model_key,
    check_omni_flash_status,
    extract_omni_workflows,
    generate_omni_flash_video,
)


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        (4, "abra_r2v_4s"),
        (6, "abra_r2v_6s"),
        (8, "abra_r2v_8s"),
        (10, "abra_r2v_10s"),
    ],
)
def test_omni_duration_model_keys(duration, expected):
    assert _load_model_key(duration) == expected


def test_invalid_duration_fails_before_submit():
    with pytest.raises(ValueError, match="duration 5s is unsupported"):
        _load_model_key(5)


def test_extract_omni_workflows_uses_primary_media_id():
    result = {
        "status": 200,
        "data": {
            "operations": [
                {
                    "operation": {"name": "operation-looking-handle"},
                    "status": "MEDIA_GENERATION_STATUS_PENDING",
                }
            ],
            "workflows": [
                {
                    "name": "workflow-1",
                    "metadata": {"primaryMediaId": "media-1"},
                }
            ],
        },
    }
    assert extract_omni_workflows(result) == [
        {"name": "workflow-1", "primary_media_id": "media-1"}
    ]


@pytest.mark.asyncio
async def test_submit_builds_flow_omni_r2v_request_and_poll_descriptor():
    client = MagicMock()
    client._client_context.return_value = {
        "projectId": "project-1",
        "tool": "PINHOLE",
        "userPaygateTier": "PAYGATE_TIER_ONE",
        "recaptchaContext": {
            "applicationType": "RECAPTCHA_APPLICATION_TYPE_WEB",
            "token": "",
        },
        "sessionId": ";old",
    }
    client._build_url.return_value = (
        "https://aisandbox-pa.googleapis.com/"
        "v1/video:batchAsyncGenerateVideoReferenceImages?key=test"
    )
    client._send = AsyncMock(
        return_value={
            "status": 200,
            "data": {
                "operations": [
                    {
                        "operation": {"name": "op-1"},
                        "status": "MEDIA_GENERATION_STATUS_PENDING",
                    }
                ],
                "workflows": [
                    {
                        "name": "workflow-1",
                        "metadata": {"primaryMediaId": "media-1"},
                    }
                ],
            },
        }
    )

    with patch("agent.services.omni_flash.get_flow_client", return_value=client):
        result = await generate_omni_flash_video(
            reference_media_ids=["ref-1", "ref-2"],
            prompt="Two friends talking in a cafe",
            project_id="project-1",
            scene_id="scene-1",
            duration_s=10,
            aspect_ratio="VIDEO_ASPECT_RATIO_LANDSCAPE",
            user_paygate_tier="PAYGATE_TIER_ONE",
            seed=123,
        )

    assert result["status"] == 200
    assert result["data"]["flowkitPolling"] == {
        "mode": "workflow_media",
        "workflows": [
            {"name": "workflow-1", "primary_media_id": "media-1"}
        ],
    }
    client._build_url.assert_called_once_with("generate_video_references")
    client._send.assert_awaited_once()

    method, params = client._send.await_args.args[:2]
    assert method == "api_request"
    assert params["captchaAction"] == "VIDEO_GENERATION"

    body = params["body"]
    assert body["useV2ModelConfig"] is True
    assert body["mediaGenerationContext"]["audioFailurePreference"] == "BLOCK_SILENCED_VIDEOS"
    assert body["clientContext"]["projectId"] == "project-1"

    request = body["requests"][0]
    assert request["videoModelKey"] == "abra_r2v_10s"
    assert request["aspectRatio"] == "VIDEO_ASPECT_RATIO_LANDSCAPE"
    assert request["seed"] == 123
    assert request["metadata"] == {"sceneId": "scene-1"}
    assert request["referenceImages"] == [
        {"mediaId": "ref-1", "imageUsageType": "IMAGE_USAGE_TYPE_ASSET"},
        {"mediaId": "ref-2", "imageUsageType": "IMAGE_USAGE_TYPE_ASSET"},
    ]


@pytest.mark.asyncio
async def test_omni_poll_pending_uses_media_endpoint_not_legacy_operation_poll():
    client = MagicMock()
    client.get_media = AsyncMock(
        return_value={
            "status": 200,
            "data": {
                "name": "media-1",
                "video": {"encodedVideo": ""},
            },
        }
    )
    client.check_video_status = AsyncMock(side_effect=AssertionError("legacy poll must not be used"))

    with patch("agent.services.omni_flash.get_flow_client", return_value=client):
        result = await check_omni_flash_status(
            [{"name": "workflow-1", "primary_media_id": "media-1"}]
        )

    client.get_media.assert_awaited_once_with("media-1")
    client.check_video_status.assert_not_awaited()
    assert result["done"] is False
    assert result["status"] == "PENDING"
    assert result["workflows"][0]["status"] == "PENDING"


@pytest.mark.asyncio
async def test_omni_poll_completed_detects_mp4_without_returning_base64_by_default():
    mp4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32
    encoded = base64.b64encode(mp4).decode()
    client = MagicMock()
    client.get_media = AsyncMock(
        return_value={
            "status": 200,
            "data": {
                "name": "media-1",
                "fifeUrl": "https://example.test/video.mp4",
                "video": {"encodedVideo": encoded},
            },
        }
    )

    with patch("agent.services.omni_flash.get_flow_client", return_value=client):
        result = await check_omni_flash_status(
            [{"name": "workflow-1", "primary_media_id": "media-1"}]
        )

    assert result["done"] is True
    assert result["status"] == "COMPLETED"
    item = result["workflows"][0]
    assert item["status"] == "MEDIA_GENERATION_STATUS_SUCCESSFUL"
    assert item["media"]["media_id"] == "media-1"
    assert item["media"]["url"] == "https://example.test/video.mp4"
    assert item["media"]["encoded_video_available"] is True
    assert "encoded_video" not in item["media"]


@pytest.mark.asyncio
async def test_omni_poll_can_return_encoded_video_when_requested():
    mp4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32
    encoded = base64.b64encode(mp4).decode()
    client = MagicMock()
    client.get_media = AsyncMock(
        return_value={"status": 200, "data": {"video": {"encodedVideo": encoded}}}
    )

    with patch("agent.services.omni_flash.get_flow_client", return_value=client):
        result = await check_omni_flash_status(
            [{"name": "workflow-1", "primary_media_id": "media-1"}],
            include_encoded_video=True,
        )

    assert result["workflows"][0]["media"]["encoded_video"] == encoded


@pytest.mark.asyncio
async def test_omni_poll_404_is_treated_as_not_ready():
    client = MagicMock()
    client.get_media = AsyncMock(return_value={"status": 404, "data": {}})

    with patch("agent.services.omni_flash.get_flow_client", return_value=client):
        result = await check_omni_flash_status(
            [{"name": "workflow-1", "primary_media_id": "media-1"}]
        )

    assert result["done"] is False
    assert result["workflows"][0]["status"] == "PENDING"


@pytest.mark.asyncio
async def test_submit_accepts_seven_references():
    client = MagicMock()
    client._client_context.return_value = {"projectId": "p"}
    client._build_url.return_value = "https://example.test/omni"
    client._send = AsyncMock(return_value={"status": 200, "data": {}})
    refs = [f"ref-{i}" for i in range(OMNI_FLASH_MAX_REFERENCE_IMAGES)]

    with patch("agent.services.omni_flash.get_flow_client", return_value=client):
        await generate_omni_flash_video(
            reference_media_ids=refs,
            prompt="test",
            project_id="p",
            duration_s=4,
        )

    request = client._send.await_args.args[1]["body"]["requests"][0]
    assert len(request["referenceImages"]) == 7


@pytest.mark.asyncio
async def test_submit_rejects_more_than_seven_references():
    refs = [f"ref-{i}" for i in range(OMNI_FLASH_MAX_REFERENCE_IMAGES + 1)]

    with pytest.raises(ValueError, match="at most 7 reference images"):
        await generate_omni_flash_video(
            reference_media_ids=refs,
            prompt="test",
            project_id="p",
            duration_s=8,
        )


@pytest.mark.asyncio
async def test_submit_rejects_first_last_style_empty_reference_set():
    with pytest.raises(ValueError, match="requires at least one reference image"):
        await generate_omni_flash_video(
            reference_media_ids=[],
            prompt="test",
            project_id="p",
            duration_s=8,
        )
