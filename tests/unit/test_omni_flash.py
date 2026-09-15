"""Unit tests for Gemini Omni Flash submissions and workflow polling.

Omni has one working surface — text-to-video on batchexecute — and three that
are not ported. So these cover three things: `_load_model_key`, the input
validation that runs before any transport is touched, and that the unported
modes say so instead of reaching for auth that is gone.

Note on `_load_model_key`: it currently has **no production caller**. Frame and
reference generation used to call it and now return early, and text-to-video
hardcodes `abra_t2v_{n}s` instead of reading models.json. The cases below pin
the mapping for when that is fixed; they are not evidence that model keys are
configurable today.

The REST and tRPC wire-contract tests that used to live here went with the
transport they asserted. They were pinned to the legacy path by a module-level
autouse fixture, which meant most of this file was testing code that no longer
runs. Git history has them if a capture ever needs a reference.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import agent.services.omni_flash as omni_flash
from agent.services.omni_flash import (
    OMNI_FLASH_MAX_REFERENCE_IMAGES,
    _load_model_key,
    check_omni_flash_status,
    extract_omni_workflows,
    generate_omni_flash_first_frame_video,
    generate_omni_flash_first_last_video,
    generate_omni_flash_text_video,
    generate_omni_flash_video,
)


# ─── model key policy (models.json, transport-independent) ──────────────────

@pytest.mark.parametrize(
    ("duration", "expected"),
    [(4, "abra_r2v_4s"), (6, "abra_r2v_6s"), (8, "abra_r2v_8s"), (10, "abra_r2v_10s")],
)
def test_omni_reference_duration_model_keys(duration, expected):
    assert _load_model_key(duration) == expected


@pytest.mark.parametrize(
    ("duration", "expected"),
    [(4, "abra_i2v_4s"), (6, "abra_i2v_6s"), (8, "abra_i2v_8s"), (10, "abra_i2v_10s")],
)
def test_omni_first_frame_model_keys(duration, expected):
    assert _load_model_key(duration, mode="frame_to_video") == expected


@pytest.mark.parametrize(
    ("duration", "expected"),
    [(4, "abra_i2v_4s"), (6, "abra_i2v_6s"), (8, "abra_i2v_8s"), (10, "abra_i2v_10s")],
)
def test_omni_first_last_model_keys_are_independently_configured(duration, expected):
    """Same family as first-frame today, but its own key so a rollout that
    splits them does not need a code release."""
    assert _load_model_key(duration, mode="start_end_frame_to_video") == expected


def test_invalid_duration_fails_before_submit():
    with pytest.raises(ValueError, match="duration 5s is unsupported"):
        _load_model_key(5)


# ─── polling descriptors ────────────────────────────────────────────────────

def test_extract_omni_workflows_uses_primary_media_id():
    """A submit carries operation-looking handles that are NOT pollable as
    operations. The workflow's primaryMediaId is the one that is."""
    result = {
        "status": 200,
        "data": {
            "operations": [
                {"operation": {"name": "operation-looking-handle"},
                 "status": "MEDIA_GENERATION_STATUS_PENDING"}
            ],
            "workflows": [
                {"name": "workflow-1", "metadata": {"primaryMediaId": "media-1"}}
            ],
        },
    }
    assert extract_omni_workflows(result) == [
        {"name": "workflow-1", "primary_media_id": "media-1"}
    ]


@pytest.mark.asyncio
async def test_batch_omni_poll_uses_as29s_media():
    client = MagicMock()
    client.get_media = AsyncMock(return_value={
        "status": 200,
        "data": {"video": {"fifeUrl": "https://flow-content.google/video/media-1?Signature=test"}},
    })
    with patch("agent.services.omni_flash.get_flow_client", return_value=client):
        result = await check_omni_flash_status([{
            "name": "workflow-1", "primary_media_id": "media-1", "project_id": "project-1",
        }])
    assert result["done"] is True
    assert result["workflows"][0]["media"]["resolved_via"] == "as29s"
    client.get_media.assert_awaited_once_with("media-1")


# ─── text-to-video: the one Omni surface on the batch path ──────────────────

@pytest.mark.asyncio
async def test_batch_text_video_builds_4s_yhhmef_submit():
    import json

    client = MagicMock()
    client._batch_project_id.return_value = "11111111-2222-3333-4444-555555555555"
    client._batch_payload = AsyncMock(return_value=[
        None, 10, [], [[
            "22222222-3333-4444-5555-666666666666",
            "11111111-2222-3333-4444-555555555555",
            "77777777-8888-9999-aaaa-bbbbbbbbbbbb", "CAE",
        ]],
    ])
    with patch("agent.services.omni_flash.get_flow_client", return_value=client):
        result = await generate_omni_flash_text_video(
            prompt="A red paper boat drifts across a pond",
            project_id="11111111-2222-3333-4444-555555555555",
            duration_s=4,
            aspect_ratio="VIDEO_ASPECT_RATIO_LANDSCAPE",
        )
    assert result["status"] == 200
    assert result["data"]["model"] == "abra_t2v_4s"
    assert result["data"]["duration_s"] == 4
    assert result["data"]["flowkitPolling"]["mode"] == "batch_media"
    rpcid, freq, captcha = client._batch_payload.await_args.args[:3]
    assert rpcid == omni_flash.fb.RPC_GEN_VIDEO_TEXT
    assert captcha == omni_flash.fb.CAPTCHA_VIDEO
    payload = json.loads(json.loads(freq)[0][0][1])
    assert payload[0][0][1] == "abra_t2v_4s"


# ─── validation runs before the capability gap is reported ──────────────────
#
# Order matters: a caller with a bad duration AND an unported mode should hear
# about the duration, which it can fix, rather than the gap, which it cannot.

@pytest.mark.asyncio
async def test_first_frame_rejects_missing_start_before_submit():
    with pytest.raises(ValueError, match="requires start_image_media_id"):
        await generate_omni_flash_first_frame_video(
            start_image_media_id="", prompt="test", project_id="p")


@pytest.mark.asyncio
async def test_first_last_rejects_missing_end_before_submit():
    with pytest.raises(ValueError, match="non-empty end_image_media_id"):
        await generate_omni_flash_first_last_video(
            start_image_media_id="start", end_image_media_id="",
            prompt="test", project_id="p")


@pytest.mark.asyncio
async def test_submit_rejects_more_than_seven_references():
    refs = [f"ref-{i}" for i in range(OMNI_FLASH_MAX_REFERENCE_IMAGES + 1)]
    with pytest.raises(ValueError, match="at most 7 reference images"):
        await generate_omni_flash_video(
            reference_media_ids=refs, prompt="test", project_id="p", duration_s=8)


@pytest.mark.asyncio
async def test_submit_rejects_empty_reference_set():
    with pytest.raises(ValueError, match="requires at least one reference image"):
        await generate_omni_flash_video(
            reference_media_ids=[], prompt="test", project_id="p", duration_s=8)


@pytest.mark.asyncio
async def test_seven_references_pass_validation_and_reach_the_capability_gap():
    """Seven is the limit, not one past it — so this must fail on the gap, not
    on the count. Guards the boundary against an off-by-one in the validator."""
    refs = [f"ref-{i}" for i in range(OMNI_FLASH_MAX_REFERENCE_IMAGES)]
    result = await generate_omni_flash_video(
        reference_media_ids=refs, prompt="test", project_id="p", duration_s=4)
    assert "UNSUPPORTED_ON_BATCH_API" in result["error"]


# ─── unported modes ─────────────────────────────────────────────────────────

class TestUnportedOmniModesAreRefusedRatherThanAttempted:
    """Frame and reference generation had only a REST implementation, and that
    transport is gone. Naming the gap beats a 401 five retries deep — and beats
    silently submitting with a Veo key, which is what a careless unification
    of these paths would do."""

    @pytest.fixture
    def client(self):
        with patch("agent.services.omni_flash.get_flow_client") as factory:
            stub = MagicMock()
            stub._send = AsyncMock()
            stub.generate_video = AsyncMock()
            factory.return_value = stub
            yield stub

    async def test_first_frame_names_the_gap_and_sends_nothing(self, client):
        result = await generate_omni_flash_first_frame_video(
            start_image_media_id="mid", prompt="go", project_id="pid")
        assert "UNSUPPORTED_ON_BATCH_API" in result["error"]
        client._send.assert_not_called()
        client.generate_video.assert_not_called()

    async def test_first_last_names_the_gap_and_sends_nothing(self, client):
        result = await generate_omni_flash_first_last_video(
            start_image_media_id="a", end_image_media_id="b",
            prompt="go", project_id="pid")
        assert "UNSUPPORTED_ON_BATCH_API" in result["error"]
        client._send.assert_not_called()
        client.generate_video.assert_not_called()

    async def test_reference_to_video_names_the_gap_and_sends_nothing(self, client):
        result = await generate_omni_flash_video(
            reference_media_ids=["a"], prompt="go", project_id="pid")
        assert "UNSUPPORTED_ON_BATCH_API" in result["error"]
        client._send.assert_not_called()
        client.generate_video.assert_not_called()

    async def test_the_message_points_to_supported_text_to_video(self, client):
        """The error is the only place a caller learns there IS a working Omni
        surface, so it names both the gap and the way round it."""
        result = await generate_omni_flash_video(
            reference_media_ids=["a"], prompt="go", project_id="pid")
        assert "text-to-video is supported" in result["error"]
        assert "reference-to-video" in result["error"]
