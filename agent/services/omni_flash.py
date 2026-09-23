"""Gemini Omni Flash video generation through the Google Flow bridge.

Migrated ``flow.google.com`` batch surfaces live-verified on 2026-09-14:

* text -> video: ``YhhmEf`` + ``abra_t2v_<duration>s`` (workflow/media polling)
* first frame -> video: ``eb1hJf`` + ``abra_i2v_<duration>s``
* first + last frame -> video: ``nprQif`` + ``omni_flash_i2v_<duration>s_first_last``
* Ingredients/references -> video: ``MZZa6b`` + ``abra_r2v_<duration>s``

Reference-conditioned modes return normal batch operation receipts and use the
same operation/media poller as migrated Veo. The legacy REST implementations are
kept below for non-batch deployments, but are not used by current production.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from urllib.parse import quote

from agent.config import USE_BATCH_RPC
from agent.services import flow_batch as fb
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
OMNI_FLASH_CREDIT_COST = {4: 7, 6: 10, 8: 12, 10: 15}
OMNI_FLASH_360P_CREDIT_COST = {4: 4, 6: 5, 8: 6, 10: 7}


async def _fetch_project_initial_data(client, project_id: str) -> dict:
    """Fetch the same authenticated project snapshot used by the Flow UI."""
    query = quote(
        json.dumps({"json": {"projectId": project_id}}, separators=(",", ":")),
        safe="",
    )
    url = f"https://labs.google/fx/api/trpc/flow.projectInitialData?input={query}"
    return await client._send(
        "trpc_request",
        {
            "url": url,
            "method": "GET",
            "headers": {"content-type": "application/json"},
        },
        timeout=15,
    )


async def _fetch_media_url(client, media_id: str) -> dict:
    """Resolve Flow's authenticated media redirect without buffering the file."""
    url = (
        "https://labs.google/fx/api/trpc/media.getMediaUrlRedirect"
        f"?name={quote(media_id, safe='')}"
    )
    return await client._send(
        "trpc_request",
        {
            "url": url,
            "method": "GET",
            "headers": {"content-type": "application/json"},
            "responseMode": "url",
        },
        timeout=15,
    )


def _validate_duration(duration_s: int) -> None:
    if duration_s not in OMNI_FLASH_VALID_DURATIONS:
        raise ValueError(
            f"Omni Flash duration {duration_s}s is unsupported; "
            f"choose one of {list(OMNI_FLASH_VALID_DURATIONS)}"
        )


def _validate_aspect(aspect_ratio: str) -> None:
    if aspect_ratio not in OMNI_FLASH_VALID_ASPECTS:
        raise ValueError(
            f"Omni Flash aspect ratio {aspect_ratio!r} is unsupported; "
            "use VIDEO_ASPECT_RATIO_PORTRAIT or VIDEO_ASPECT_RATIO_LANDSCAPE"
        )


def _validate_resolution(resolution: str) -> str:
    value = str(resolution or "720p").strip().lower()
    if value not in {"360p", "720p"}:
        raise ValueError("Omni Flash resolution must be 360p or 720p")
    return value


def _batch_operation_result(operation, project_id: str, model: str, duration_s: int, resolution: str) -> dict:
    pending = {
        "operation": {"name": operation.operation_id},
        "status": "MEDIA_GENERATION_STATUS_PENDING",
    }
    return {
        "status": 200,
        "data": {
            "operations": [pending],
            "model": model,
            "duration_s": duration_s,
            "resolution": resolution,
            "flowkitPolling": {
                "mode": "batch_operation",
                "project_id": project_id,
                "operations": [pending],
            },
        },
    }


def _load_model_key(duration_s: int, mode: str = "reference_to_video") -> str:
    """Resolve a configured Omni Flash model key for ``mode`` + duration."""
    _validate_duration(duration_s)

    with open(_MODELS_FILE, encoding="utf-8") as f:
        models = json.load(f)

    key = (
        models.get("omni_flash_models", {})
        .get(mode, {})
        .get(str(duration_s))
    )
    if not key:
        raise ValueError(
            f"No Omni Flash model key configured for mode {mode!r}, {duration_s}s"
        )
    return key


def _validate_reference_inputs(
    reference_media_ids: list[str],
    duration_s: int,
    aspect_ratio: str,
) -> list[str]:
    _validate_duration(duration_s)
    _validate_aspect(aspect_ratio)

    refs = [mid for mid in (reference_media_ids or []) if isinstance(mid, str) and mid]
    if not refs:
        raise ValueError("Omni Flash requires at least one reference image")
    if len(refs) > OMNI_FLASH_MAX_REFERENCE_IMAGES:
        raise ValueError(
            f"Omni Flash accepts at most {OMNI_FLASH_MAX_REFERENCE_IMAGES} reference images"
        )
    return refs


def _validate_frame_inputs(
    start_image_media_id: str,
    end_image_media_id: str | None,
    duration_s: int,
    aspect_ratio: str,
) -> None:
    _validate_duration(duration_s)
    _validate_aspect(aspect_ratio)
    if not isinstance(start_image_media_id, str) or not start_image_media_id:
        raise ValueError("Omni Flash first-frame generation requires start_image_media_id")
    if end_image_media_id is not None and (
        not isinstance(end_image_media_id, str) or not end_image_media_id
    ):
        raise ValueError("Omni Flash First+Last requires a non-empty end_image_media_id")


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
    item = {"name": name, "primary_media_id": primary_media_id}
    project_id = workflow.get("project_id") or workflow.get("projectId")
    if isinstance(project_id, str) and project_id:
        item["project_id"] = project_id
    return item


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


def _annotate_polling(result: dict, project_id: str) -> dict:
    """Add an explicit FlowKit polling descriptor to a successful submit."""
    workflows = extract_omni_workflows(result)
    if not workflows:
        return result
    data = result.get("data") if isinstance(result.get("data"), dict) else result
    if isinstance(data, dict):
        for workflow in workflows:
            workflow["project_id"] = project_id
        data["flowkitPolling"] = {
            "mode": "project_media",
            "project_id": project_id,
            "workflows": workflows,
        }
    return result


async def generate_omni_flash_text_video(
    prompt: str,
    project_id: str,
    scene_id: str = "",
    duration_s: int = 8,
    resolution: str = "720p",
    aspect_ratio: str = "VIDEO_ASPECT_RATIO_PORTRAIT",
    user_paygate_tier: str = "PAYGATE_TIER_ONE",
    seed: int | None = None,
) -> dict:
    """Submit Omni 1.1 Flash text-to-video on the migrated Flow batch API."""
    _validate_duration(duration_s)
    resolution = _validate_resolution(resolution)
    _validate_aspect(aspect_ratio)
    if not USE_BATCH_RPC:
        return {
            "error": "Omni text-to-video is implemented on the flow.google.com batch path only"
        }

    client = get_flow_client()
    try:
        pid = client._batch_project_id(project_id)
        model_key = f"abra_t2v_{duration_s}s" + ("_360p" if resolution == "360p" else "")
        freq = fb.text_video_request(
            prompt,
            pid,
            aspect=aspect_ratio,
            model=model_key,
            resolution=resolution,
        )
        payload = await client._batch_payload(
            fb.RPC_GEN_VIDEO_TEXT,
            freq,
            fb.CAPTCHA_VIDEO,
            timeout=120,
        )
        submitted = fb.read_text_video_submit(payload)
    except Exception as exc:
        return {"status": 502, "error": f"{type(exc).__name__}: {exc}"}

    media_id = submitted["media_id"]
    workflow = {
        "name": submitted.get("workflow_id") or media_id,
        "primary_media_id": media_id,
        "project_id": pid,
    }
    return {
        "status": 200,
        "data": {
            "media": [{"name": media_id}],
            "workflows": [workflow],
            "model": model_key,
            "duration_s": duration_s,
            "resolution": resolution,
            "flowkitPolling": {
                "mode": "batch_media",
                "project_id": pid,
                "workflows": [workflow],
            },
        },
    }


async def _submit_omni_frame_video(
    *,
    start_image_media_id: str,
    end_image_media_id: str | None,
    prompt: str,
    project_id: str,
    scene_id: str = "",
    duration_s: int = 8,
    resolution: str = "720p",
    aspect_ratio: str = "VIDEO_ASPECT_RATIO_PORTRAIT",
    user_paygate_tier: str = "PAYGATE_TIER_ONE",
    seed: int | None = None,
) -> dict:
    """Submit Omni first-frame or First+Last generation.

    Batch payloads were live-captured from ``flow.google.com`` on 2026-09-14:
    first-frame uses ``eb1hJf``; First+Last uses ``nprQif``. Both return normal
    batch operations and are polled through ``/api/flow/check-status``.
    """
    _validate_frame_inputs(start_image_media_id, end_image_media_id, duration_s, aspect_ratio)
    resolution = _validate_resolution(resolution)
    mode = "start_end_frame_to_video" if end_image_media_id is not None else "frame_to_video"
    model_key = _load_model_key(duration_s, mode=mode)
    client = get_flow_client()

    if USE_BATCH_RPC:
        try:
            pid = client._batch_project_id(project_id)
            if end_image_media_id is None:
                freq = fb.omni_first_frame_request(
                    prompt, pid, start_image_media_id, duration_s=duration_s,
                    resolution=resolution, aspect=aspect_ratio,
                )
                rpcid = fb.RPC_GEN_VIDEO
                batch_model = f"abra_i2v_{duration_s}s" + ("_360p" if resolution == "360p" else "")
            else:
                freq = fb.omni_first_last_request(
                    prompt, pid, start_image_media_id, end_image_media_id,
                    duration_s=duration_s, resolution=resolution, aspect=aspect_ratio,
                )
                rpcid = fb.RPC_GEN_VIDEO_FIRST_LAST
                batch_model = f"omni_flash_i2v_{duration_s}s_first_last" + (
                    "_360p" if resolution == "360p" else ""
                )
            payload = await client._batch_payload(
                rpcid, freq, fb.CAPTCHA_VIDEO, timeout=120,
            )
            operation = fb.read_operation(payload)
            client._remember_operation(operation.operation_id, pid)
        except Exception as exc:
            return {"status": 502, "error": f"{type(exc).__name__}: {exc}"}
        return _batch_operation_result(operation, pid, batch_model, duration_s, resolution)

    endpoint = "generate_video_start_end" if end_image_media_id is not None else "generate_video"
    ts = int(time.time() * 1000)
    request_item = {
        "aspectRatio": aspect_ratio,
        "textInput": {"structuredPrompt": {"parts": [{"text": prompt}]}},
        "videoModelKey": model_key,
        "seed": seed if seed is not None else ts % 1_000_000,
        "metadata": {"sceneId": scene_id} if scene_id else {},
        "startImage": {"mediaId": start_image_media_id},
    }
    if end_image_media_id is not None:
        request_item["endImage"] = {"mediaId": end_image_media_id}
    context = client._client_context(project_id, user_paygate_tier)
    body = {
        "mediaGenerationContext": {"batchId": str(uuid.uuid4())},
        "clientContext": {**context, "sessionId": f";{ts}"},
        "requests": [request_item],
        "useV2ModelConfig": True,
    }
    result = await client._send(
        "api_request",
        {
            "url": client._build_url(endpoint),
            "method": "POST",
            "headers": random_headers(),
            "body": body,
            "captchaAction": "VIDEO_GENERATION",
        },
        timeout=60,
    )
    return _annotate_polling(result, project_id)


async def generate_omni_flash_first_frame_video(
    start_image_media_id: str,
    prompt: str,
    project_id: str,
    scene_id: str = "",
    duration_s: int = 8,
    resolution: str = "720p",
    aspect_ratio: str = "VIDEO_ASPECT_RATIO_PORTRAIT",
    user_paygate_tier: str = "PAYGATE_TIER_ONE",
    seed: int | None = None,
) -> dict:
    """Submit Omni Flash First frame -> video."""
    return await _submit_omni_frame_video(
        start_image_media_id=start_image_media_id,
        end_image_media_id=None,
        prompt=prompt,
        project_id=project_id,
        scene_id=scene_id,
        duration_s=duration_s,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        user_paygate_tier=user_paygate_tier,
        seed=seed,
    )


async def generate_omni_flash_first_last_video(
    start_image_media_id: str,
    end_image_media_id: str,
    prompt: str,
    project_id: str,
    scene_id: str = "",
    duration_s: int = 8,
    resolution: str = "720p",
    aspect_ratio: str = "VIDEO_ASPECT_RATIO_PORTRAIT",
    user_paygate_tier: str = "PAYGATE_TIER_ONE",
    seed: int | None = None,
) -> dict:
    """Submit Omni Flash First + Last frame -> video."""
    return await _submit_omni_frame_video(
        start_image_media_id=start_image_media_id,
        end_image_media_id=end_image_media_id,
        prompt=prompt,
        project_id=project_id,
        scene_id=scene_id,
        duration_s=duration_s,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        user_paygate_tier=user_paygate_tier,
        seed=seed,
    )


async def generate_omni_flash_video(
    reference_media_ids: list[str],
    prompt: str,
    project_id: str,
    scene_id: str = "",
    duration_s: int = 8,
    resolution: str = "720p",
    aspect_ratio: str = "VIDEO_ASPECT_RATIO_PORTRAIT",
    user_paygate_tier: str = "PAYGATE_TIER_ONE",
    seed: int | None = None,
) -> dict:
    """Submit Omni Flash Ingredients/reference-to-video generation.

    The migrated UI uses RPC ``MZZa6b`` with ``abra_r2v_<duration>s`` (720p)
    or ``abra_r2v_<duration>s_360p``. Batch jobs use normal operation polling.
    """
    refs = _validate_reference_inputs(reference_media_ids, duration_s, aspect_ratio)
    resolution = _validate_resolution(resolution)
    model_key = _load_model_key(duration_s, mode="reference_to_video")
    client = get_flow_client()

    if USE_BATCH_RPC:
        try:
            pid = client._batch_project_id(project_id)
            freq = fb.omni_reference_video_request(
                prompt, pid, refs, duration_s=duration_s,
                resolution=resolution, aspect=aspect_ratio,
            )
            payload = await client._batch_payload(
                fb.RPC_GEN_VIDEO_REFERENCES, freq, fb.CAPTCHA_VIDEO, timeout=120,
            )
            operation = fb.read_operation(payload)
            client._remember_operation(operation.operation_id, pid)
        except Exception as exc:
            return {"status": 502, "error": f"{type(exc).__name__}: {exc}"}
        batch_model = f"abra_r2v_{duration_s}s" + ("_360p" if resolution == "360p" else "")
        return _batch_operation_result(operation, pid, batch_model, duration_s, resolution)

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
    return _annotate_polling(result, project_id)


async def _check_omni_batch_media(
    workflows: list[dict],
    include_encoded_video: bool = False,
    project_id: str = "",
) -> dict:
    normalized = [item for workflow in (workflows or []) if (item := _normalize_workflow(workflow))]
    if not normalized:
        raise ValueError(
            "Omni polling requires workflow descriptors with name and primary_media_id"
        )
    resolved_project_id = project_id or next(
        (item.get("project_id", "") for item in normalized if item.get("project_id")),
        "",
    )
    client = get_flow_client()
    items = []
    for workflow in normalized:
        media_id = workflow["primary_media_id"]
        response = await client.get_media(media_id)
        data = response.get("data") if isinstance(response, dict) else None
        video = data.get("video") if isinstance(data, dict) else None
        url = video.get("fifeUrl") if isinstance(video, dict) else None
        if isinstance(url, str) and url.startswith("https://flow-content.google/video/"):
            media = {
                "media_id": media_id,
                "url": url,
                "encoded_video_available": False,
                "resolved_via": "as29s",
            }
            if include_encoded_video:
                media["encoded_video"] = None
            items.append({
                "name": workflow["name"],
                "primary_media_id": media_id,
                "project_id": workflow.get("project_id") or resolved_project_id,
                "done": True,
                "status": "MEDIA_GENERATION_STATUS_SUCCESSFUL",
                "error": None,
                "media": media,
            })
        else:
            items.append({
                "name": workflow["name"],
                "primary_media_id": media_id,
                "project_id": workflow.get("project_id") or resolved_project_id,
                "done": False,
                "status": "PENDING",
                "error": None,
            })
    all_done = bool(items) and all(item["done"] for item in items)
    return {
        "project_id": resolved_project_id or None,
        "done": all_done,
        "status": "COMPLETED" if all_done else "PENDING",
        "workflows": items,
    }


async def check_omni_flash_status(
    workflows: list[dict],
    include_encoded_video: bool = False,
    project_id: str = "",
) -> dict:
    """Perform one non-blocking poll pass for Omni workflow-backed jobs."""
    if USE_BATCH_RPC:
        return await _check_omni_batch_media(workflows, include_encoded_video, project_id)
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

    resolved_project_id = project_id or next(
        (item.get("project_id", "") for item in normalized if item.get("project_id")),
        "",
    )
    if not resolved_project_id:
        raise ValueError(
            "Omni project polling requires project_id. Use the project_id returned "
            "inside flowkitPolling or pass project_id explicitly."
        )
    if any(
        item.get("project_id") and item["project_id"] != resolved_project_id
        for item in normalized
    ):
        raise ValueError(
            "All Omni workflows in one poll must belong to the same project_id"
        )

    client = get_flow_client()
    response = await _fetch_project_initial_data(client, resolved_project_id)
    http_status = response.get("status") if isinstance(response, dict) else None
    if isinstance(http_status, int) and http_status >= 400:
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        error = data.get("error") if isinstance(data, dict) else None
        if isinstance(error, dict):
            error = error.get("message") or error.get("code")
        raise RuntimeError(
            error
            or response.get("error")
            or f"Flow project poll failed: API_{http_status}"
        )

    envelope = response.get("data") if isinstance(response, dict) else None
    result = envelope.get("result") if isinstance(envelope, dict) else None
    result_data = result.get("data") if isinstance(result, dict) else None
    project_json = result_data.get("json") if isinstance(result_data, dict) else None
    contents = project_json.get("projectContents") if isinstance(project_json, dict) else None
    if not isinstance(contents, dict):
        raise RuntimeError("Flow project poll returned an unexpected response shape")

    project_workflows = contents.get("workflows")
    project_media = contents.get("media")
    project_workflows = project_workflows if isinstance(project_workflows, list) else []
    project_media = project_media if isinstance(project_media, list) else []
    known_workflow_names = {
        item.get("name")
        for item in project_workflows
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    media_by_id = {
        item.get("name"): item
        for item in project_media
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    media_by_workflow = {
        item.get("workflowId"): item
        for item in project_media
        if isinstance(item, dict) and isinstance(item.get("workflowId"), str)
    }

    items = []

    for workflow in normalized:
        name = workflow["name"]
        media_id = workflow["primary_media_id"]
        payload = media_by_id.get(media_id) or media_by_workflow.get(name)
        if not isinstance(payload, dict):
            items.append({
                "name": name,
                "primary_media_id": media_id,
                "project_id": resolved_project_id,
                "done": False,
                "status": "PENDING",
                "error": None,
                "workflow_present": name in known_workflow_names,
            })
            continue

        metadata = payload.get("mediaMetadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        media_status = metadata.get("mediaStatus")
        media_status = media_status if isinstance(media_status, dict) else {}
        generation_status = media_status.get("mediaGenerationStatus")

        if isinstance(generation_status, str) and (
            generation_status.endswith("FAILED") or generation_status.endswith("CANCELLED")
        ):
            items.append({
                "name": name,
                "primary_media_id": media_id,
                "project_id": resolved_project_id,
                "done": True,
                "status": "FAILED",
                "error": generation_status,
            })
            continue

        if generation_status != "MEDIA_GENERATION_STATUS_SUCCESSFUL":
            items.append({
                "name": name,
                "primary_media_id": media_id,
                "project_id": resolved_project_id,
                "done": False,
                "status": "PENDING",
                "error": None,
            })
            continue

        url = None
        url_error = None
        url_response = await _fetch_media_url(client, media_id)
        if isinstance(url_response, dict) and url_response.get("status", 500) < 400:
            url_data = url_response.get("data")
            candidate = url_data.get("url") if isinstance(url_data, dict) else None
            if isinstance(candidate, str) and candidate.startswith("https://flow-content.google/"):
                url = candidate
            else:
                url_error = "Flow media redirect returned no allowed URL"
        else:
            url_error = (
                url_response.get("error")
                if isinstance(url_response, dict)
                else "Flow media redirect failed"
            )
        item = {
            "name": name,
            "primary_media_id": media_id,
            "project_id": resolved_project_id,
            "done": True,
            "status": "MEDIA_GENERATION_STATUS_SUCCESSFUL",
            "error": None,
            "media": {
                "media_id": media_id,
                "url": url,
                "encoded_video_available": False,
            },
        }
        if include_encoded_video:
            item["media"]["encoded_video"] = None
        if url_error:
            item["media"]["url_error"] = url_error
        items.append(item)

    all_done = bool(items) and all(item["done"] for item in items)
    any_failed = any(item.get("status") == "FAILED" for item in items)
    return {
        "project_id": resolved_project_id,
        "done": all_done,
        "status": "FAILED" if any_failed else ("COMPLETED" if all_done else "PENDING"),
        "workflows": items,
    }
