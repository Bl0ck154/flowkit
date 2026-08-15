"""Headless polling for Flow video upscales.

Google Flow's upsampler currently returns workflow descriptors whose logical
``primaryMediaId`` may not appear in ``flow.projectInitialData``.  The browser UI
can still resolve completed media through ``media.getMediaUrlRedirect``.

This module exposes a small active poller that treats a successful authenticated
media redirect as the completion signal, avoiding the legacy
``batchCheckAsyncVideoGenerationStatus`` and ``/v1/media/{id}`` paths.
"""

from __future__ import annotations

from urllib.parse import quote

from agent.services.flow_client import get_flow_client

_ALLOWED_MEDIA_URL_PREFIX = "https://flow-content.google/"


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


def extract_upscale_workflows(result: dict) -> list[dict]:
    """Extract ``name`` + ``primaryMediaId`` descriptors from an upscale submit."""
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


def annotate_upscale_polling(result: dict) -> dict:
    """Attach an explicit headless polling descriptor to a successful submit."""
    workflows = extract_upscale_workflows(result)
    if not workflows:
        return result

    data = result.get("data") if isinstance(result.get("data"), dict) else result
    if isinstance(data, dict):
        data["flowkitPolling"] = {
            "mode": "media_redirect",
            "workflows": workflows,
        }
    return result


async def _fetch_media_url(client, media_id: str) -> dict:
    """Resolve Flow's authenticated media redirect without buffering video."""
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


def _parse_media_redirect(response: dict) -> tuple[str | None, str | None, str | None]:
    """Return ``(url, content_type, diagnostic)`` for one redirect probe."""
    if not isinstance(response, dict):
        return None, None, "Flow media redirect returned an invalid response"

    status = response.get("status")
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    candidate = data.get("url")
    content_type = data.get("contentType")

    if (
        isinstance(status, int)
        and status < 400
        and isinstance(candidate, str)
        and candidate.startswith(_ALLOWED_MEDIA_URL_PREFIX)
    ):
        return candidate, content_type if isinstance(content_type, str) else None, None

    error = response.get("error")
    if not error and isinstance(status, int) and status >= 400:
        error = f"API_{status}"
    if not error and isinstance(candidate, str):
        # When the upsample is not ready, fetch may finish on the tRPC endpoint
        # itself rather than the signed media URL. Treat that as pending.
        error = "media redirect not ready"
    if not error:
        error = "media redirect not ready"

    return None, content_type if isinstance(content_type, str) else None, str(error)


async def check_upscale_status(
    workflows: list[dict],
    include_encoded_video: bool = False,
) -> dict:
    """Perform one non-blocking active poll pass for Flow upsample workflows.

    Unlike Omni generation, upsampled workflow/media entries may never surface
    in ``flow.projectInitialData``.  Completion is therefore detected by asking
    Flow to resolve the logical ``primaryMediaId`` directly through
    ``media.getMediaUrlRedirect``.

    A valid ``https://flow-content.google/...`` redirect means the output is
    ready. Any other response remains ``PENDING`` and includes probe diagnostics
    so callers can keep polling with their own timeout/backoff.
    """
    normalized = []
    for workflow in workflows or []:
        item = _normalize_workflow(workflow)
        if item:
            normalized.append(item)

    if not normalized:
        raise ValueError(
            "Upscale polling requires workflow descriptors with name and "
            "primary_media_id (or raw Flow metadata.primaryMediaId)"
        )

    client = get_flow_client()
    items = []

    for workflow in normalized:
        media_id = workflow["primary_media_id"]
        response = await _fetch_media_url(client, media_id)
        url, content_type, diagnostic = _parse_media_redirect(response)

        if url:
            media = {
                "media_id": media_id,
                "url": url,
                "encoded_video_available": False,
                "resolved_via": "media.getMediaUrlRedirect",
            }
            if content_type:
                media["content_type"] = content_type
            if include_encoded_video:
                media["encoded_video"] = None

            items.append(
                {
                    "name": workflow["name"],
                    "primary_media_id": media_id,
                    "done": True,
                    "status": "MEDIA_GENERATION_STATUS_SUCCESSFUL",
                    "error": None,
                    "media": media,
                }
            )
            continue

        probe = {}
        if isinstance(response, dict):
            if isinstance(response.get("status"), int):
                probe["http_status"] = response["status"]
            data = response.get("data")
            if isinstance(data, dict) and isinstance(data.get("url"), str):
                probe["resolved_url"] = data["url"]
        if diagnostic:
            probe["diagnostic"] = diagnostic

        item = {
            "name": workflow["name"],
            "primary_media_id": media_id,
            "done": False,
            "status": "PENDING",
            "error": None,
        }
        if probe:
            item["probe"] = probe
        items.append(item)

    all_done = bool(items) and all(item["done"] for item in items)
    return {
        "done": all_done,
        "status": "COMPLETED" if all_done else "PENDING",
        "workflows": items,
    }
