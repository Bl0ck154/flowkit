"""Muse2APIProvider — MediaProvider adapter for a muse2api gateway.

    Flow Kit worker ──> Muse2APIProvider ──HTTP──> muse2api ──> muse.ai

muse2api (https://github.com/crisng95/muse2api) wraps the muse.ai web app in
an OpenAI-compatible API and owns everything upstream: the account pool,
failover, cooldowns and the browser driver. This provider only translates a
:class:`ProviderJob` into gateway calls and the answer back into the
Flow-shaped result dict the rest of the pipeline parses, so scenes rendered
here look exactly like Flow or assistant output downstream.

Finished media is downloaded into ``output/_shared/muse2api/`` and recorded as
a ``file://`` URL. Gateway media links are only as durable as the gateway's
data dir (and only reachable where the gateway is), and ``file://`` URLs
never expire, so ``/fk-refresh-urls`` has nothing to do for them.

What muse.ai can and cannot do shapes the capabilities:

* image         — text-to-image, with up to four entity refs sent inline as
                  data URLs (extra refs are dropped, logged).
* video (i2v)   — first frame + prompt.
* chained video — no end-frame input: fails unless MUSE2API_ALLOW_DEGRADED=1,
                  which drops the end frame and renders plain i2v.
* video_refs    — only with MUSE2API_ALLOW_DEGRADED=1, as i2v off the scene
                  image (or the first reference).
* edit_image, upscale, audio — not offered (``/v1/images/edits`` is 501).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from agent import config
from agent.sdk.services.assistant_provider import _image_result, _video_result
from agent.sdk.services.provider_base import (
    KIND_IMAGE,
    KIND_VIDEO,
    KIND_VIDEO_REFS,
    MediaProvider,
    ProviderCapabilities,
    ProviderJob,
)
from agent.services.muse2api_client import (
    MAX_IMAGE_REFS,
    Muse2APIClient,
    Muse2APIError,
    to_data_url,
)
from agent.utils.paths import file_url_to_path

logger = logging.getLogger(__name__)

_ASPECT = {"VERTICAL": "9:16", "HORIZONTAL": "16:9"}
_VIDEO_EXT = {"video/mp4": "mp4", "video/webm": "webm", "video/quicktime": "mov"}


def _image_ext(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return "png"


class Muse2APIProvider(MediaProvider):
    """Renders media through a muse2api gateway over HTTP."""

    name = "muse2api"
    display_name = "Muse (muse2api gateway)"

    def __init__(self, client: Muse2APIClient | None = None) -> None:
        self.client = client or Muse2APIClient(
            config.MUSE2API_URL, config.MUSE2API_KEY,
            timeout_s=config.MUSE2API_TIMEOUT_S, poll_s=config.MUSE2API_POLL_S,
        )
        self.allow_degraded = config.MUSE2API_ALLOW_DEGRADED
        self.output_dir = config.SHARED_OUTPUT_DIR / "muse2api"
        # Per instance, because r2v is only on offer when degrading is allowed.
        self.capabilities = ProviderCapabilities(
            generate_image=True,
            edit_image=False,
            generate_video_i2v=True,
            generate_video_r2v=self.allow_degraded,
            upscale=False,
            generate_audio=False,
            max_concurrent=config.MUSE2API_MAX_CONCURRENT,
            cooldown_s=config.MUSE2API_COOLDOWN_S,
        )

    def is_available(self) -> bool:
        """Available once MUSE2API_URL is set. Gateway health (accounts, driver)
        is the gateway's business: a request it cannot serve fails with its
        own error code and is retried by the worker like any other failure."""
        return self.client.configured

    def check(self, job: ProviderJob) -> str | None:
        if not self.client.configured:
            return "muse2api provider is not configured — set MUSE2API_URL"
        if job.kind == KIND_VIDEO_REFS and not self.allow_degraded:
            return ("muse2api has no reference-to-video input — set "
                    "MUSE2API_ALLOW_DEGRADED=1 to render it as i2v off the scene image")
        return super().check(job)

    # ── MediaProvider interface ──

    async def run(self, job: ProviderJob) -> dict:
        try:
            if job.kind == KIND_IMAGE:
                return await self._run_image(job)
            if job.kind in (KIND_VIDEO, KIND_VIDEO_REFS):
                return await self._run_video(job)
        except Muse2APIError as e:
            logger.error("muse2api: job %s (%s) failed: %s", job.job_id[:12], job.kind, e)
            return {"error": str(e)}
        except (OSError, ValueError, httpx.HTTPError) as e:
            # Unreadable or unreachable input image, full disk, bad base64 …
            logger.error("muse2api: job %s (%s) failed: %s", job.job_id[:12], job.kind, e)
            return {"error": f"muse2api: {e}"}
        return {"error": f"muse2api provider does not support job kind '{job.kind}'"}

    async def _run_image(self, job: ProviderJob) -> dict:
        prompt = job.prompt
        composition = (job.extra or {}).get("composition")
        if composition:
            prompt = f"{prompt}\n\nComposition: {composition}"
        refs = list(dict.fromkeys(job.reference_urls or []))
        if len(refs) > MAX_IMAGE_REFS:
            logger.warning("muse2api: job %s — %d reference images, the gateway takes "
                           "%d; dropping the rest", job.job_id[:12], len(refs), MAX_IMAGE_REFS)
            refs = refs[:MAX_IMAGE_REFS]
        # An unreadable ref fails the job (OSError/ValueError in run()) rather
        # than quietly rendering a scene without its character.
        images = [await to_data_url(ref) for ref in refs]
        data = await self.client.generate_image(
            prompt, model=config.MUSE2API_IMAGE_MODEL, size=_ASPECT.get(job.orientation),
            images=images or None)
        url = await self._save(job.job_id, data, _image_ext(data))
        mid = str(uuid.uuid4())
        logger.info("muse2api: image %s ready (media_id=%s)", job.job_id[:12], mid[:8])
        return _image_result(mid, url)

    async def _run_video(self, job: ProviderJob) -> dict:
        prefix = "vertical" if job.orientation == "VERTICAL" else "horizontal"
        start = job.start_url
        if job.kind == KIND_VIDEO_REFS:
            start = start or (job.reference_urls[0] if job.reference_urls else None)
            if not start:
                return {"error": "No valid reference images for r2v"}
            logger.warning("muse2api: job %s — r2v degraded to i2v", job.job_id[:12])
        if not start:
            return {"error": f"No {prefix} image for scene"}
        if job.end_url:
            if not self.allow_degraded:
                return {"error": "muse2api has no end-frame input for chained video — "
                                 "set MUSE2API_ALLOW_DEGRADED=1 to render plain i2v"}
            logger.warning("muse2api: job %s — end frame dropped, rendering plain i2v",
                           job.job_id[:12])

        image = await to_data_url(start)
        seconds = int(job.duration_s) if job.duration_s else config.MUSE2API_VIDEO_SECONDS
        task = await self.client.create_video(
            job.prompt, model=config.MUSE2API_VIDEO_MODEL,
            size=_ASPECT.get(job.orientation), seconds=seconds, image=image)
        task_id = task.get("id")
        if not task_id:
            return {"error": "muse2api: video task created without an id"}
        logger.info("muse2api: video %s submitted as %s", job.job_id[:12], task_id)

        result = await self.client.wait_video(task_id)
        data = await self.client.download(result["url"])
        ext = _VIDEO_EXT.get((result.get("mime") or "").split(";")[0], "mp4")
        url = await self._save(job.job_id, data, ext)
        mid = str(uuid.uuid4())
        logger.info("muse2api: video %s ready (media_id=%s)", job.job_id[:12], mid[:8])
        return _video_result(mid, url)

    async def _save(self, job_id: str, data: bytes, ext: str) -> str:
        path = self.output_dir / f"{job_id}.{ext}"

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await asyncio.to_thread(_write)
        return "file://" + str(path.resolve())

    async def register_existing_image(
        self, url: str, *, name: str = "", project_id: str = ""
    ) -> dict:
        """Mint a UUID for an image we already have — the gateway has no ids."""
        parsed = urlparse(url or "")
        if parsed.scheme in ("http", "https"):
            canonical = url
        else:
            local = file_url_to_path(url) if parsed.scheme == "file" else Path(url)
            if not local or not local.is_file():
                return {"error": f"muse2api: local image not found for '{name}': {url}"}
            canonical = url if parsed.scheme == "file" else ("file://" + str(local.resolve()))
        mid = str(uuid.uuid4())
        logger.info("muse2api: registered existing image '%s' → media_id=%s", name, mid[:8])
        return {"data": {"media": [{"name": mid}], "url": canonical}}
