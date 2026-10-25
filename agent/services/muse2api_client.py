"""HTTP client for a muse2api gateway (https://github.com/crisng95/muse2api).

muse2api exposes the muse.ai web app as an OpenAI-compatible API. Flow Kit
only needs the media half of it:

    POST /v1/images/generations   prompt (+ up to 4 refs) -> image   (synchronous)
    POST /v1/videos               prompt (+first frame) -> task
    GET  /v1/videos/{task_id}     task status; result.url when succeeded
    GET  /v1/media/{name}         download generated media (public)
    GET  /readyz                  driver health + available accounts

Every ``/v1/*`` call carries ``Authorization: Bearer <MUSE2API_KEY>``. Errors
come back as an OpenAI error body (``{"error": {"message", "type", "code"}}``)
and are raised here as :class:`Muse2APIError` carrying that code, so the
provider can report ``no_account_available`` / ``upstream_quota_exhausted``
and the rest verbatim instead of a bare HTTP status.

Input images are always sent inline as data URLs. Flow Kit's own media lives
at ``file://`` paths (or signed URLs only this machine can reach), and the
gateway may run on another host, so letting it fetch URLs itself would break
as soon as the two are split.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from agent.utils.paths import file_url_to_path

logger = logging.getLogger(__name__)

TERMINAL_OK = "succeeded"
#: The gateway's ``image`` field on /v1/images/generations takes up to four refs.
MAX_IMAGE_REFS = 4
TERMINAL_FAILED = ("failed", "cancelled")


class Muse2APIError(Exception):
    """A muse2api call failed. ``code`` is the gateway's error code when known."""

    def __init__(self, message: str, *, status: int | None = None, code: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code

    def __str__(self) -> str:
        prefix = f"muse2api {self.code}" if self.code else "muse2api"
        if self.status:
            prefix += f" (HTTP {self.status})"
        return f"{prefix}: {self.message}"


def _error_from_response(resp: httpx.Response) -> Muse2APIError:
    try:
        body = resp.json()
    except ValueError:
        body = None
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        return Muse2APIError(err.get("message") or resp.reason_phrase,
                             status=resp.status_code, code=err.get("code") or "")
    return Muse2APIError(resp.text[:300] or resp.reason_phrase, status=resp.status_code)


async def to_data_url(ref: str, *, timeout: float = 60.0) -> str:
    """Turn a file:// path, local path, http(s) URL or data URL into a data URL."""
    ref = (ref or "").strip()
    if not ref:
        raise ValueError("empty image reference")
    if ref.startswith("data:"):
        return ref
    parsed = urlparse(ref)
    if parsed.scheme in ("http", "https"):
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(ref)
            resp.raise_for_status()
            data = resp.content
            mime = resp.headers.get("content-type", "").split(";")[0].strip()
        mime = mime or mimetypes.guess_type(parsed.path)[0] or "image/png"
    else:
        path = file_url_to_path(ref) if parsed.scheme == "file" else Path(ref)
        if not path or not path.is_file():
            raise FileNotFoundError(f"image not found: {ref}")
        data = await asyncio.to_thread(path.read_bytes)
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


class Muse2APIClient:
    """Thin async client for the muse2api media endpoints."""

    def __init__(self, base_url: str, api_key: str = "", *,
                 timeout_s: float = 1800.0, poll_s: float = 5.0,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.poll_s = poll_s
        self._transport = transport  # tests inject httpx.MockTransport here

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def _url(self, path: str) -> str:
        return path if path.startswith(("http://", "https://")) else f"{self.base_url}{path}"

    async def _request(self, method: str, path: str, *, timeout: float = 60.0,
                       **kwargs) -> dict:
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                resp = await client.request(method, self._url(path),
                                            headers=self._headers(), **kwargs)
        except httpx.TimeoutException as e:
            raise Muse2APIError(f"{method} {path} timed out after {timeout:.0f}s",
                                code="timeout") from e
        except httpx.HTTPError as e:
            raise Muse2APIError(f"{method} {path} failed: {e}",
                                code="connection_error") from e
        if resp.status_code >= 400:
            raise _error_from_response(resp)
        try:
            return resp.json()
        except ValueError as e:
            raise Muse2APIError(f"{method} {path} returned non-JSON",
                                status=resp.status_code) from e

    # ── Health ──

    async def readyz(self) -> dict:
        return await self._request("GET", "/readyz", timeout=10.0)

    # ── Images ──

    async def generate_image(self, prompt: str, *, model: str, size: str | None,
                             images: list[str] | None = None) -> bytes:
        """Generate one image and return its bytes (b64_json: no second download).

        ``images`` are reference images as data URLs; the gateway attaches
        them to the muse.ai chat and takes at most :data:`MAX_IMAGE_REFS`.
        """
        body = {"prompt": prompt, "model": model, "n": 1, "response_format": "b64_json"}
        if size:
            body["size"] = size
        if images:
            body["image"] = images[:MAX_IMAGE_REFS]
        data = await self._request("POST", "/v1/images/generations",
                                   json=body, timeout=self.timeout_s)
        items = data.get("data") or []
        if not items:
            raise Muse2APIError("image generation returned no data", code="empty_result")
        item = items[0]
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        if item.get("url"):
            return await self.download(item["url"])
        raise Muse2APIError("image generation returned neither b64_json nor url",
                            code="empty_result")

    # ── Videos ──

    async def create_video(self, prompt: str, *, model: str, size: str | None,
                           seconds: int | None, image: str | None) -> dict:
        body: dict = {"prompt": prompt, "model": model}
        if size:
            body["size"] = size
        if seconds:
            body["seconds"] = seconds
        if image:
            body["image"] = image
        return await self._request("POST", "/v1/videos", json=body, timeout=120.0)

    async def get_video(self, task_id: str) -> dict:
        return await self._request("GET", f"/v1/videos/{task_id}", timeout=30.0)

    async def wait_video(self, task_id: str) -> dict:
        """Poll a video task until it finishes. Returns the task's ``result``."""
        deadline = time.monotonic() + self.timeout_s
        transient = 0
        while True:
            try:
                task = await self.get_video(task_id)
                transient = 0
            except Muse2APIError as e:
                # A blip on the poll is not a failed render; a 404 is (the
                # gateway restarted and lost the task, or the id is wrong).
                if e.status == 404 or transient >= 3:
                    raise
                transient += 1
                logger.warning("muse2api: poll %s failed (%s), retrying", task_id, e)
                task = {}
            status = (task.get("status") or "").lower()
            if status == TERMINAL_OK:
                result = task.get("result") or {}
                if not result.get("url"):
                    raise Muse2APIError(f"video task {task_id} succeeded without a url",
                                        code="empty_result")
                return result
            if status in TERMINAL_FAILED:
                raise Muse2APIError(task.get("error") or f"video task {task_id} {status}",
                                    code=f"task_{status}")
            if time.monotonic() >= deadline:
                raise Muse2APIError(f"video task {task_id} still '{status or '?'}' after "
                                    f"{self.timeout_s:.0f}s", code="timeout")
            await asyncio.sleep(self.poll_s)

    # ── Media ──

    async def download(self, url: str) -> bytes:
        """Fetch generated media. ``/v1/media`` is public, but a key never hurts."""
        try:
            async with httpx.AsyncClient(timeout=300.0, follow_redirects=True,
                                         transport=self._transport) as client:
                resp = await client.get(self._url(url), headers=self._headers())
        except httpx.HTTPError as e:
            raise Muse2APIError(f"download {url} failed: {e}",
                                code="connection_error") from e
        if resp.status_code >= 400:
            raise _error_from_response(resp)
        return resp.content
