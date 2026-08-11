"""Gemini Omni Flash video generation through the Google Flow bridge.

Omni Flash is a separate video family from Veo. Google Flow currently
submits reference-conditioned Omni jobs through
``batchAsyncGenerateVideoReferenceImages`` using ``abra_r2v_<duration>s``
model keys.

Important: Omni submit responses may contain operation-looking handles, but
those handles are not compatible with the legacy
``batchCheckAsyncVideoGenerationStatus`` polling endpoint. Omni jobs are
workflow-backed and must be polled through ``/v1/media/<primaryMediaId>``.
"""

from __future__ import annotations

import base64
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

    refs = [mid for mid in (reference_media_ids or []) if isinstance(mid, str) and mid]
    if not refs:
        raise ValueError("Omni Flash requires at least one reference image")
    if len(refs) > OMNI_FLASH_MAX_REFERENCE_IMAGES:
        raise ValueError(
            f"Omni Flash accepts at most {OMNI_FLASH_MAX_REFERENCE_IMAGES} reference images"
        )

    if duration_s not in OMNI_FLASH_VALID_DURATIONS:
        raise ValueError(
            f"Omni Flash duration {duration_s}s is unsupported; "
            f"choose one of {list(OMNI_FLASH_VALID_DURATIONS)}"
        )
    return refs


def _normalize_workflow(workflow: dict) -> dict | None:
    """Normalize a raw Flow workflow or FlowKit polling descriptor."""
    if not isinstance(workflow, dict):
        return None
    name = workflow.get("name")
    primary_media_id = workflow.get("primary_media_id")
    if not primary_media_id:
        metadata = workflow.get("metadata")
        if isinstance(metadata, dict):
            primary_media_id = metadata.get("primaryMediaId")
    if not isinstance(name, str) or not name:
        return None
    if not isinstance(primary_media_id, str) or not primary_media_id:
        return None
    return {"name": name, "primary_media_id": primary_media_id}


def extract_omni_workflows(result: dict) -> list[dict]:
    """Extract ``name`` + ``primaryMediaId`` pairs from an Omni submit."""
    if not isinstance(result, dict):
        return []
    data = result.get("data") if isinstance(result.get("data"), dict) else result
    workflows = data.get("workflows", []) if isinstance(data, dict) else []
    normalized = []
    for workflow in workflows:
        item = _normalize_workflow(workflow)
        if item:
            normalized.append(item)
    return normalized


def _annotate_polling(result: dict) -> dict:
    """Add an explicit FlowKit polling descriptor to a successful submit."""
    workflows = extract_omni_workflows(result)
    if not workflows:
        return result
    data = result.get("data") if isinstance(result.get("data"), dict) else result
    if isinstance(data, dict):
        data["flowkitPolling"] = {
            "mode": "workflow_media",
            "workflows": workflows,
        }
    return result


def _is_complete_mp4(encoded: str) -> bool:
    """Flow can expose a small placeholder payload before the final MP4."""
    if not isinstance(encoded, str) or not encoded:
        return False
    try:
        binary = base64.b64decode(encoded, validate=False)
    except Exception:
        return False
    return len(binary) >= 12 and binary[4:8] == b"ftyp"


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

    Successful responses are annotated with ``data.flowkitPolling`` containing
    the workflow names and primary media IDs required by the Omni polling path.
    Do not feed Omni operation handles to ``check_video_status``.
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
            "audioFailurePreference": "BLOCK_SILENCED_VIDEOS",
        },
        "clientContext": {**context, "sessionId": f";{ts}"},
        "requests": [request_item],
        "useV2ModelConfig": True,
    }

    url = client._build_url("generate_video_references")
    result = await client._send(
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
    return _annotate_polling(result)


async def check_omni_flash_status(
    workflows: list[dict],
    include_encoded_video: bool = False,
) -> dict:
    """Perform one non-blocking poll pass for Omni workflow-backed jobs.

    Each workflow is polled via ``GET /v1/media/<primaryMediaId>``. A completed
    result is only reported once ``video.encodedVideo`` decodes to an MP4
    (``ftyp`` box present), matching Flow's current workflow behavior.
    """
    normalized = []
    for workflow in workflows or []:
        item = _normalize_workflow(workflow)
        if item:
            normalized.append(item)
    if not normalized:
        raise ValueError(
            "Omni polling requires workflow descriptors with name and primary_media_id "
            "(or raw Flow metadata.primaryMediaId)"
        )

    client = get_flow_client()
    items = []

    for workflow in normalized:
        name = workflow["name"]
        media_id = workflow["primary_media_id"]
        response = await client.get_media(media_id)

        http_status = response.get("status") if isinstance(response, dict) else None
        if isinstance(http_status, int) and http_status >= 400:
            if http_status == 404:
                items.append({
                    "name": name,
                    "primary_media_id": media_id,
                    "done": False,
                    "status": "PENDING",
                    "error": None,
                })
                continue
            data = response.get("data") if isinstance(response.get("data"), dict) else {}
            error = data.get("error") if isinstance(data, dict) else None
            error_message = None
            if isinstance(error, dict):
                error_message = error.get("message") or error.get("status")
            items.append({
                "name": name,
                "primary_media_id": media_id,
                "done": True,
                "status": "FAILED",
                "error": error_message or response.get("error") or f"API_{http_status}",
            })
            continue

        payload = response.get("data") if isinstance(response, dict) and isinstance(response.get("data"), dict) else response
        payload = payload if isinstance(payload, dict) else {}
        video = payload.get("video") if isinstance(payload.get("video"), dict) else {}
        encoded = video.get("encodedVideo") if isinstance(video, dict) else None

        media_status = payload.get("mediaMetadata") if isinstance(payload.get("mediaMetadata"), dict) else {}
        media_status = media_status.get("mediaStatus") if isinstance(media_status.get("mediaStatus"), dict) else {}
        generation_status = media_status.get("mediaGenerationStatus") if isinstance(media_status, dict) else None

        if isinstance(generation_status, str) and generation_status.endswith("FAILED"):
            items.append({
                "name": name,
                "primary_media_id": media_id,
                "done": True,
                "status": "FAILED",
                "error": generation_status,
            })
            continue

        if not _is_complete_mp4(encoded):
            items.append({
                "name": name,
                "primary_media_id": media_id,
                "done": False,
                "status": "PENDING",
                "error": None,
            })
            continue

        url = None
        if isinstance(video, dict):
            url = video.get("fifeUrl") or video.get("servingUri")
        url = url or payload.get("fifeUrl") or payload.get("servingUri")
        item = {
            "name": name,
            "primary_media_id": media_id,
            "done": True,
            "status": "MEDIA_GENERATION_STATUS_SUCCESSFUL",
            "error": None,
            "media": {
                "media_id": media_id,
                "url": url if isinstance(url, str) else None,
                "encoded_video_available": True,
            },
        }
        if include_encoded_video:
            item["media"]["encoded_video"] = encoded
        items.append(item)

    all_done = bool(items) and all(item["done"] for item in items)
    any_failed = any(item.get("status") == "FAILED" for item in items)
    return {
        "done": all_done,
        "status": "FAILED" if any_failed else ("COMPLETED" if all_done else "PENDING"),
        "workflows": items,
    }
