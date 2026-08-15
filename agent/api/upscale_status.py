"""Direct headless polling endpoint for Flow video upscales."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.services.flow_client import get_flow_client
from agent.services.upscale_polling import check_upscale_status

router = APIRouter(prefix="/flow", tags=["flow"])


class CheckUpscaleStatusRequest(BaseModel):
    workflows: list[dict]
    include_encoded_video: bool = False


@router.post("/check-upscale-status")
async def check_upscale(body: CheckUpscaleStatusRequest):
    """Resolve completed upsample media without opening the Flow project UI.

    Pass the raw ``workflows`` array returned by ``POST /api/flow/upscale-video``.
    The poller probes ``media.getMediaUrlRedirect`` for each workflow's
    ``metadata.primaryMediaId`` and returns ``PENDING`` until Flow exposes a
    signed ``flow-content.google`` video URL.
    """
    client = get_flow_client()
    if not client.connected:
        raise HTTPException(503, "Extension not connected")

    try:
        return await check_upscale_status(
            body.workflows,
            include_encoded_video=body.include_encoded_video,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
