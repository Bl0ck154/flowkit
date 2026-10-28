#!/usr/bin/env python3
"""Reference worker for the FlowKit provider-job queue.

This script implements the *worker side* of the provider-job protocol against
the FlowKit HTTP API (``/api/provider-jobs``). It is the counterpart to
``AssistantProvider.run()`` (the producer side), which inserts QUEUED rows and
blocks until a worker finishes them.

Protocol (equivalent curl shown for agents that prefer raw HTTP):

    # 1. Long-poll for the next claimable job (claims it atomically, lease granted)
    GET /api/provider-jobs/wait-next?provider=assistant&worker_id=w1&timeout_s=60
    #   -> 200 + job row, or 204 when nothing arrives before the timeout

    # 2. While working, extend the lease (every ~lease_ttl/3; default ttl 300s)
    POST /api/provider-jobs/{id}/heartbeat   {"worker_id": "w1", "lease_ttl_s": 300}
    #    Only the lease holder may heartbeat / progress / complete / fail.
    #    complete/fail are idempotent: repeating them on an already-terminal
    #    job returns the existing row; a stranger's attempt gets 409.

    # 3. Optionally report progress
    POST /api/provider-jobs/{id}/progress    {"worker_id": "w1", "progress": 50, "message": "rendering"}

    # 4. Finish
    POST /api/provider-jobs/{id}/complete   {"worker_id": "w1", "result": {"output_url": "...", "media_id": "<uuid>"}}
    # or
    POST /api/provider-jobs/{id}/fail       {"worker_id": "w1", "error": "..."}

The job row carries everything needed to generate::

    {"id": ..., "kind": "image|edit_image|i2v|r2v|upscale",
     "prompt": ..., "orientation": "VERTICAL|HORIZONTAL",
     "source_url": ..., "end_url": ...,
     "extra": {"reference_urls": [...], "aspect": ..., ...}}

``complete`` expects ``result.output_url`` — a ``file://`` or ``https://`` URL
of the finished media — and an optional ``result.media_id`` (a UUID is minted
when absent).

To build a real worker, replace :func:`process_job` with actual generation
(image/video model calls, uploads, ...). The protocol loop, leasing, and
heartbeat plumbing below are reusable as-is via :class:`ProviderJobClient`.

Usage:
    python -m agent.worker.assistant_worker --provider assistant --worker-id pax-1
    python -m agent.worker.assistant_worker --once   # process a single job then exit
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import aiohttp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("assistant_worker")


class ProviderJobClient:
    """Thin async client for the /api/provider-jobs worker endpoints."""

    def __init__(self, api_base: str, worker_id: str, lease_ttl_s: float = 300):
        self.api_base = api_base.rstrip("/")
        self.worker_id = worker_id
        self.lease_ttl_s = lease_ttl_s
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *exc):
        if self._session:
            await self._session.close()
            self._session = None

    def _url(self, path: str) -> str:
        return f"{self.api_base}/provider-jobs{path}"

    async def wait_next(self, provider: str, timeout_s: float = 60) -> dict | None:
        """Long-poll for the next claimable job; returns the claimed row or None."""
        assert self._session is not None
        params = {"provider": provider, "worker_id": self.worker_id,
                  "lease_ttl_s": self.lease_ttl_s, "timeout_s": timeout_s}
        async with self._session.get(self._url("/wait-next"), params=params) as resp:
            if resp.status == 204:
                return None
            resp.raise_for_status()
            return await resp.json()

    async def heartbeat(self, job_id: str) -> dict:
        assert self._session is not None
        async with self._session.post(
                self._url(f"/{job_id}/heartbeat"),
                json={"worker_id": self.worker_id, "lease_ttl_s": self.lease_ttl_s}) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def progress(self, job_id: str, pct: int, message: str | None = None) -> None:
        assert self._session is not None
        async with self._session.post(
                self._url(f"/{job_id}/progress"),
                json={"worker_id": self.worker_id,
                      "progress": pct, "message": message}) as resp:
            resp.raise_for_status()

    async def complete(self, job_id: str, output_url: str,
                       media_id: str | None = None) -> dict:
        assert self._session is not None
        result = {"output_url": output_url}
        if media_id:
            result["media_id"] = media_id
        async with self._session.post(
                self._url(f"/{job_id}/complete"),
                json={"worker_id": self.worker_id,
                      "result": result}) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def fail(self, job_id: str, error: str) -> dict:
        assert self._session is not None
        async with self._session.post(
                self._url(f"/{job_id}/fail"),
                json={"worker_id": self.worker_id,
                      "error": error}) as resp:
            resp.raise_for_status()
            return await resp.json()


# ---------------------------------------------------------------------------
# Generation hook — replace this with real media generation.
# ---------------------------------------------------------------------------

async def process_job(job: dict, client: ProviderJobClient) -> dict:
    """Generate the media for *job*.

    Return ``{"output_url": ..., "media_id": ...}`` (media_id optional).
    Raise on failure — the caller reports it via ``/fail``.

    The default implementation is a stub: subclass or monkeypatch this
    function with a real image/video backend.
    """
    raise NotImplementedError(
        "process_job is a stub — implement generation for job kind "
        f"'{job.get('kind')}' (prompt: {job.get('prompt', '')[:80]!r}) and return "
        '{"output_url": ..., "media_id": ...}, or complete the job via the '
        "HTTP API from your own agent loop.")


# ---------------------------------------------------------------------------
# Worker loop
# ---------------------------------------------------------------------------

async def _heartbeat_loop(client: ProviderJobClient, job_id: str,
                          stop: asyncio.Event) -> None:
    """Extend the lease until the job is done."""
    interval = max(5.0, client.lease_ttl_s / 3)
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
        if stop.is_set():
            break
        try:
            await client.heartbeat(job_id)
            logger.debug("heartbeat ok for %s", job_id[:12])
        except Exception as e:
            logger.warning("heartbeat failed for %s: %s", job_id[:12], e)


async def _handle_one(client: ProviderJobClient, job: dict) -> None:
    job_id = job["id"]
    logger.info("claimed job %s kind=%s prompt=%r",
                job_id[:12], job.get("kind"), job.get("prompt", "")[:80])
    stop = asyncio.Event()
    hb = asyncio.ensure_future(_heartbeat_loop(client, job_id, stop))
    try:
        result = await process_job(job, client)
        await client.complete(job_id, result["output_url"], result.get("media_id"))
        logger.info("job %s completed: %s", job_id[:12], result.get("output_url", "")[:80])
    except Exception as e:
        logger.exception("job %s failed", job_id[:12])
        try:
            await client.fail(job_id, f"{type(e).__name__}: {e}")
        except Exception:
            logger.warning("could not report failure for %s", job_id[:12])
    finally:
        stop.set()
        await hb


async def run_worker(api_base: str, provider: str, worker_id: str,
                     lease_ttl_s: float, once: bool = False) -> None:
    async with ProviderJobClient(api_base, worker_id, lease_ttl_s) as client:
        logger.info("worker %s listening for provider=%s at %s",
                    worker_id, provider, api_base)
        while True:
            job = await client.wait_next(provider, timeout_s=60)
            if job is None:
                if once:
                    logger.info("no job available, exiting (--once)")
                    return
                continue
            await _handle_one(client, job)
            if once:
                return


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Reference worker for FlowKit provider jobs")
    p.add_argument("--api", default="http://localhost:8000/api",
                   help="FlowKit API base (default: http://localhost:8000/api)")
    p.add_argument("--provider", default="assistant",
                   help="provider queue to consume (default: assistant)")
    p.add_argument("--worker-id", default="worker-1",
                   help="unique id for this worker (used for lease ownership)")
    p.add_argument("--lease-ttl", type=float, default=300,
                   help="lease seconds per heartbeat (default: 300)")
    p.add_argument("--once", action="store_true",
                   help="process a single job (or none) then exit")
    args = p.parse_args(argv)
    try:
        asyncio.run(run_worker(args.api, args.provider, args.worker_id,
                               args.lease_ttl, args.once))
    except KeyboardInterrupt:
        logger.info("interrupted, exiting")
    return 0


if __name__ == "__main__":
    sys.exit(main())
