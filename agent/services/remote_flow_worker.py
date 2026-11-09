"""Remote trusted-browser worker for captcha-gated Flow UI generation.

The server remains responsible for API shape, project/media bookkeeping and
polling. Only the composer interaction + Generate click is delegated to a
signed-in browser on the user's normal network.

This transport never mints or replays a captcha token. The remote browser
drives Flow's UI and observes the batchexecute response emitted by Flow itself.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict
from typing import Any

from agent.services.flow_ui_generation import (
    _IMAGE_MODEL_LABELS,
    _image_aspect_icon,
    _picker_asb_url,
    _video_aspect_icon,
    _video_model_label,
    parse_generation_spec,
)

logger = logging.getLogger(__name__)

_worker: Any | None = None
_pending: dict[str, asyncio.Future[dict]] = {}
_worker_meta: dict[str, Any] = {}


def connected() -> bool:
    return _worker is not None


def status() -> dict[str, Any]:
    return {
        "connected": connected(),
        "meta": dict(_worker_meta),
        "pending": len(_pending),
    }


def project_scope() -> str:
    """Return a stable namespace for Flow projects owned by the active browser."""
    if not connected():
        return "server"
    worker_id = str(_worker_meta.get("workerId") or "").strip()
    return f"remote:{worker_id}" if worker_id else "remote:legacy"


async def set_worker(websocket: Any) -> None:
    global _worker, _worker_meta
    previous = _worker
    _worker = websocket
    _worker_meta = {}
    if previous is not None and previous is not websocket:
        try:
            await previous.close(code=4001, reason="Replaced by newer worker")
        except Exception:
            pass
    logger.info("Remote Flow UI worker connected")


def clear_worker(websocket: Any) -> None:
    global _worker, _worker_meta
    if _worker is not websocket:
        return
    _worker = None
    _worker_meta = {}
    for future in list(_pending.values()):
        if not future.done():
            future.set_result({"status": 503, "error": "REMOTE_FLOW_WORKER_DISCONNECTED"})
    _pending.clear()
    logger.info("Remote Flow UI worker disconnected")


async def handle_message(data: dict[str, Any], websocket: Any) -> None:
    global _worker_meta
    if websocket is not _worker:
        return
    if data.get("type") == "worker_ready":
        _worker_meta = {
            "extensionVersion": data.get("extensionVersion"),
            "workerId": data.get("workerId"),
            "browser": data.get("browser"),
            "flowUrl": data.get("flowUrl"),
        }
        logger.info("Remote Flow UI worker ready version=%s", _worker_meta.get("extensionVersion"))
        return
    request_id = str(data.get("id") or "")
    if not request_id:
        return
    future = _pending.pop(request_id, None)
    if future is None or future.done():
        return
    if data.get("error"):
        future.set_result({
            "status": int(data.get("status") or 502),
            "error": str(data.get("error")),
        })
        return

    result = data.get("result")
    if isinstance(result, dict):
        future.set_result(result)
        return

    # Generic batch_rpc responses from the extension use the legacy bridge
    # shape {id, status, data} instead of {id, result}. Accept both so the
    # trusted local browser can own project/upload/poll RPCs as well as UI
    # generation.
    if "status" in data or "data" in data:
        future.set_result({
            "status": int(data.get("status") or 200),
            "data": data.get("data", ""),
        })
        return

    future.set_result({"status": 502, "error": "REMOTE_FLOW_WORKER_BAD_RESPONSE"})


async def run_remote_batch_rpc(
    rpcid: str,
    freq: str,
    *,
    captcha_action: str | None = None,
    match: str | None = None,
    timeout: float = 60,
) -> dict:
    worker = _worker
    if worker is None:
        return {"status": 503, "error": "REMOTE_FLOW_WORKER_NOT_CONNECTED"}

    request_id = uuid.uuid4().hex
    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict] = loop.create_future()
    _pending[request_id] = future
    payload = {
        "id": request_id,
        "method": "batch_rpc",
        "params": {
            "rpcid": rpcid,
            "freq": freq,
            "captchaAction": captcha_action,
            "match": match,
        },
    }
    try:
        await worker.send(json.dumps(payload))
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.CancelledError:
        _pending.pop(request_id, None)
        raise
    except asyncio.TimeoutError:
        _pending.pop(request_id, None)
        return {"status": 504, "error": "REMOTE_FLOW_WORKER_BATCH_TIMEOUT"}
    except Exception as exc:
        _pending.pop(request_id, None)
        return {"status": 502, "error": f"REMOTE_FLOW_WORKER_BATCH_SEND_FAILED: {exc}"}


async def _picker_tokens(project_id: str, media_ids: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for media_id in media_ids:
        if not media_id or media_id in out:
            continue
        url = await _picker_asb_url(project_id, media_id)
        if not url or "/asb/" not in url:
            raise RuntimeError(f"Flow media {media_id} has no picker thumbnail mapping")
        out[media_id] = url.split("/asb/", 1)[1].split("?", 1)[0]
    return out


async def run_remote_ui_generation(
    rpcid: str,
    freq: str,
    *,
    project_id: str | None = None,
    timeout: float = 120,
) -> dict:
    worker = _worker
    if worker is None:
        return {"status": 503, "error": "REMOTE_FLOW_WORKER_NOT_CONNECTED"}

    spec = parse_generation_spec(rpcid, freq)
    pid = str(project_id or spec.project_id or "")
    if not pid:
        return {"status": 422, "error": "REMOTE_FLOW_WORKER_NO_PROJECT"}
    spec.project_id = pid

    media_ids = [
        spec.start_media_id,
        spec.end_media_id,
        *spec.reference_media_ids,
    ]
    media_ids = [str(value) for value in media_ids if value]
    try:
        picker_tokens = await _picker_tokens(pid, media_ids)
    except Exception as exc:
        return {"status": 502, "error": f"REMOTE_FLOW_WORKER_MEDIA_LOOKUP_FAILED: {exc}"}

    ui: dict[str, Any] = {
        "modeIcon": "image" if spec.kind == "image" else "videocam",
        "aspectIcon": _image_aspect_icon(spec.aspect) if spec.kind == "image" else _video_aspect_icon(spec.aspect),
        "countLabel": f"x{max(1, min(4, spec.count))}" if spec.kind == "image" else "x1",
    }
    if spec.kind == "image":
        ui["modelLabel"] = _IMAGE_MODEL_LABELS.get(spec.model, "Nano Banana 2")
    else:
        ui.update({
            "submodeIcon": "crop_free" if spec.kind in {"first_frame", "first_last"} else "chrome_extension",
            "modelLabel": _video_model_label(spec.model),
            "resolutionLabel": spec.resolution,
            "durationLabel": str(spec.duration_s) if spec.duration_s else None,
        })

    request_id = uuid.uuid4().hex
    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict] = loop.create_future()
    _pending[request_id] = future
    payload = {
        "id": request_id,
        "method": "ui_generate",
        "params": {
            "rpcid": rpcid,
            "projectId": pid,
            "spec": asdict(spec),
            "ui": ui,
            "pickerTokens": picker_tokens,
            "reloadBeforeMedia": bool(media_ids),
        },
    }
    try:
        await worker.send(json.dumps(payload))
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.CancelledError:
        _pending.pop(request_id, None)
        raise
    except asyncio.TimeoutError:
        _pending.pop(request_id, None)
        return {"status": 504, "error": "REMOTE_FLOW_WORKER_TIMEOUT"}
    except Exception as exc:
        _pending.pop(request_id, None)
        return {"status": 502, "error": f"REMOTE_FLOW_WORKER_SEND_FAILED: {exc}"}


async def run_remote_ui_debug(project_id: str, timeout: float = 20) -> dict:
    worker = _worker
    if worker is None:
        return {"status": 503, "error": "REMOTE_FLOW_WORKER_NOT_CONNECTED"}
    pid = str(project_id or "").strip()
    if not pid:
        return {"status": 422, "error": "REMOTE_FLOW_WORKER_NO_PROJECT"}
    request_id = uuid.uuid4().hex
    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict] = loop.create_future()
    _pending[request_id] = future
    payload = {
        "id": request_id,
        "method": "ui_debug",
        "params": {"projectId": pid},
    }
    try:
        await worker.send(json.dumps(payload))
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.CancelledError:
        _pending.pop(request_id, None)
        raise
    except asyncio.TimeoutError:
        _pending.pop(request_id, None)
        return {"status": 504, "error": "REMOTE_FLOW_WORKER_DEBUG_TIMEOUT"}
    except Exception as exc:
        _pending.pop(request_id, None)
        return {"status": 502, "error": f"REMOTE_FLOW_WORKER_DEBUG_SEND_FAILED: {exc}"}
