"""Gemini Omni Flash video generation through the Google Flow bridge.

Omni Flash is a separate video family from Veo.  Google Flow currently
submits reference-conditioned Omni jobs through the same
``batchAsyncGenerateVideoReferenceImages`` route used by R2V, but selects an
``abra_r2v_<duration>s`` model key.  Keep the model keys in ``models.json`` so
they can be updated without changing this client.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from agent.services.flow_client import get_flow_client
from agent.services.headers import random_headers

_MODELS_FILE = Path(__file__).parent.parent / "models.json"

OMNI_FLASH_VALID_DURATIONS = (4, 6, 8, 10)
OMNI_FLASH_VALID_ASPECTS = {
    "VIDEO_ASPECT_RATIO_PORTRAIT",
    "VIDEO_ASPECT_RATIO_LANDSCAPE",
}
OMNI_FLASH_MAX_REFERENCE_IMAGES = 7
# Informational only. Flow pricing can be promotional/variable.
OMNI_FLASH_CREDIT_COST = {4: 15, 6: 20, 8: 25, 10: 30}


def _load_model_key(duration_s: int) -> str:
    """Resolve the configured Omni Flash R2V key for a duration."""
    if duration_s not in OMNI_FLASH_VALID_DURATIONS:
        raise ValueError(
            f"Omni Flash duration {duration_s}s is unsupported; "
            f"choose one of {list(OMNI_FLASH_VALID_DURATIONS)}"
        )

    with open(_MODELS_FILE, encoding="utf-8") as f:
        models = json.load(f)

    key = (
        models.get("omni_flash_models", {})
        .get("reference_to_video", {})
        .get(str(duration_s))
    )
    if not key:
        raise ValueError(f"No Omni Flash model key configured for {duration_s}s")
    return key


def _validate_inputs(reference_media_ids: list[str], duration_s: int, aspect_ratio: str) -> list[str]:
    if aspect_ratio not in OMNI_FLASH_VALID_ASPECTS:
        raise ValueError(
            f"Omni Flash aspect ratio {aspect_ratio!r} is unsupported; "
            "use VIDEO_ASPECT_RATIO_PORTRAIT or VIDEO_ASPECT_RATIO_LANDSCAPE"
        )

    # Preserve caller ordering while filtering accidental empty values.
    refs = [mid for mid in (reference_media_ids or []) if isinstance(mid, str) and mid]
    if not refs:
        raise ValueError("Omni Flash requires at least one reference image")
    if len(refs) > OMNI_FLASH_MAX_REFERENCE_IMAGES:
        raise ValueError(
            f"Omni Flash accepts at most {OMNI_FLASH_MAX_REFERENCE_IMAGES} reference images"
        )

    # Validate duration before a request reaches the browser/credits path.
    if duration_s not in OMNI_FLASH_VALID_DURATIONS:
        raise ValueError(
            f"Omni Flash duration {duration_s}s is unsupported; "
            f"choose one of {list(OMNI_FLASH_VALID_DURATIONS)}"
        )
    return refs


async def generate_omni_flash_video(
    reference_media_ids: list[str],
    prompt: str,
    project_id: str,
    scene_id: str = "",
    duration_s: int = 8,
    aspect_ratio: str = "VIDEO_ASPECT_RATIO_PORTRAIT",
    user_paygate_tier: str = "PAYGATE_TIER_ONE",
    seed: int | None = None,
) -> dict:
    """Submit an Omni Flash reference-to-video generation.

    The return value intentionally matches FlowClient's existing video-submit
    envelope, so callers can reuse ``/flow/check-status`` and the normal Flow
    operation polling path.
    """
    refs = _validate_inputs(reference_media_ids, duration_s, aspect_ratio)
    model_key = _load_model_key(duration_s)
    client = get_flow_client()

    ts = int(time.time() * 1000)
    request_item = {
        "aspectRatio": aspect_ratio,
        "textInput": {"structuredPrompt": {"parts": [{"text": prompt}]}},
        "videoModelKey": model_key,
        "seed": seed if seed is not None else ts % 1_000_000,
        "metadata": {"sceneId": scene_id} if scene_id else {},
        "referenceImages": [
            {"mediaId": mid, "imageUsageType": "IMAGE_USAGE_TYPE_ASSET"}
            for mid in refs
        ],
    }

    context = client._client_context(project_id, user_paygate_tier)
    body = {
        "mediaGenerationContext": {
            "batchId": str(uuid.uuid4()),
            # Match current Google Flow Omni submissions: a silent-audio output
            # is treated as a failed generation rather than a degraded success.
            "audioFailurePreference": "BLOCK_SILENCED_VIDEOS",
        },
        "clientContext": {**context, "sessionId": f";{ts}"},
        "requests": [request_item],
        "useV2ModelConfig": True,
    }

    url = client._build_url("generate_video_references")
    return await client._send(
        "api_request",
        {
            "url": url,
            "method": "POST",
            "headers": random_headers(),
            "body": body,
            "captchaAction": "VIDEO_GENERATION",
        },
        timeout=60,
    )
