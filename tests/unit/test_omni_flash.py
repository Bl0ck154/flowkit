"""Unit tests for Gemini Omni Flash Flow submissions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.services.omni_flash import (
    OMNI_FLASH_MAX_REFERENCE_IMAGES,
    _load_model_key,
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


@pytest.mark.asyncio
async def test_submit_builds_flow_omni_r2v_request():
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
                ]
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
