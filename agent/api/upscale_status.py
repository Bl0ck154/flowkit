"""Explicit Full HD / 4K export endpoints for Google Flow videos."""

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.services.flow_client import get_flow_client
from agent.services.flow_poll import annotate_polling, check_workflow_status
from agent.services.flow_project_session import ensure_session_project

router = APIRouter(prefix="/flow", tags=["flow"])


class ExportVideoRequest(BaseModel):
    media_id: str
    scene_id: str = "export"
    quality: Literal["1080p", "4k"] = "1080p"
    aspect_ratio: str = "VIDEO_ASPECT_RATIO_LANDSCAPE"
    project_id: str | None = None


class CheckExportStatusRequest(BaseModel):
    workflows: list[dict]


@router.post("/export-video")
async def export_video(body: ExportVideoRequest):
    """Start Google's native Full HD/4K export.

    This is the same Flow upsample operation exposed by the UI, presented as an
    export/download-quality choice. 1080p is the default because Omni Flash's
    generated file is normally 720p and Full HD is the expected downloadable
    master.
    """
    client = get_flow_client()
    if not client.connected:
        raise HTTPException(503, "Extension not connected")

    resolution = (
        "VIDEO_RESOLUTION_1080P"
        if body.quality == "1080p"
        else "VIDEO_RESOLUTION_4K"
    )
    # An export is scoped to a real Flow project. A direct caller may omit
    # project_id, in which case allocate/reuse the leased session project.
    project_id = str(body.project_id or "").strip()
    if not project_id:
        try:
            session = await ensure_session_project(client)
            project_id = str(session.get("project_id") or "")
        except Exception as exc:
            raise HTTPException(502, f"Could not create Flow session project: {exc}") from exc
        if not project_id:
            raise HTTPException(502, "Flow session project did not return an id")

    result = await client.upscale_video(
        media_id=body.media_id,
        scene_id=body.scene_id,
        aspect_ratio=body.aspect_ratio,
        resolution=resolution,
        project_id=project_id,
    )
    if result.get("error") or (
        isinstance(result.get("status"), int) and result["status"] >= 400
    ):
        status = result.get("status")
        http_status = status if isinstance(status, int) and 400 <= status <= 599 else 502
        raise HTTPException(http_status, result.get("error", result.get("data")))

    annotated = annotate_polling(result, mode="media_redirect", project_id=project_id)
    data = annotated.get("data", annotated)
    if isinstance(data, dict):
        data["export"] = {
            "quality": body.quality,
            "resolution": resolution,
            "native_flow_export": True,
            "next": "/api/flow/check-status",
            "check_status_mode": "export",
        }
    return data


# Backward-compatible aliases retained for existing fork clients.
# New callers use /api/flow/check-status with mode=export.
@router.post("/check-export-status", deprecated=True)
@router.post("/check-upscale-status", include_in_schema=False)
async def check_export_status(body: CheckExportStatusRequest):
    """Return a signed downloadable URL when the native Flow export is ready."""
    client = get_flow_client()
    if not client.connected:
        raise HTTPException(503, "Extension not connected")
    try:
        result = await check_workflow_status(
            body.workflows, mode="media_redirect", client=client,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if result.get("status") == "COMPLETED":
        result["download_ready"] = True
    else:
        result["download_ready"] = False
    return result
