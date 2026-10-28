"""Tests for the assistant media provider (provider-job queue transport).

pytest-asyncio runs in AUTO mode (see pytest.ini), so these are native
async tests — no manual event-loop juggling.
"""
import asyncio
import json

import pytest

from agent.db import crud
from agent.sdk.services import assistant_provider as ap
from agent.sdk.services.provider_base import (
    KIND_EDIT_IMAGE,
    KIND_IMAGE,
    KIND_UPSCALE,
    KIND_VIDEO,
    ProviderJob,
)
from agent.sdk.services.result_handler import parse_result
from agent.worker._parsing import _is_uuid

SAMPLE_UUID = "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def provider():
    prov = ap.AssistantProvider()
    prov.timeout_s = 30
    prov.poll_s = 0.05
    return prov


def _image_job(job_id="jobimg123456", **kw):
    args = dict(job_id=job_id, kind=KIND_IMAGE, prompt="a cat",
                orientation="VERTICAL")
    args.update(kw)
    return ProviderJob(**args)


async def _fake_worker(job_id, result=None, fail=None, delay=0.2):
    """Simulate an external worker: wait for the row, claim, finish."""
    for _ in range(200):
        if await crud.get_provider_job(job_id):
            break
        await asyncio.sleep(0.05)
    claimed = await crud.claim_provider_job(job_id, "w1", lease_ttl_s=60)
    assert claimed is not None
    await asyncio.sleep(delay)
    if fail:
        await crud.fail_provider_job(job_id, "w1", fail)
    else:
        await crud.complete_provider_job(job_id, "w1", result or {})


async def test_run_queues_job_and_returns_worker_result(test_db, provider):
    job_id = "jobimg123456"
    task = asyncio.ensure_future(_fake_worker(
        job_id, result={"output_url": "file:///tmp/out.png", "media_id": SAMPLE_UUID}))

    result = await provider.run(_image_job(job_id))
    await task

    assert not result.get("error"), result
    gen = parse_result(result, "GENERATE_IMAGE")
    assert gen.success
    assert gen.media_id == SAMPLE_UUID
    assert gen.url == "file:///tmp/out.png"

    row = await crud.get_provider_job(job_id)
    assert row["status"] == "SUCCEEDED"
    assert row["provider"] == "assistant"
    assert row["kind"] == KIND_IMAGE
    assert json.loads(row["extra"])["reference_urls"] == []


async def test_run_mints_media_id_when_worker_omits_it(test_db, provider):
    job_id = "jobimgmint01"
    task = asyncio.ensure_future(_fake_worker(
        job_id, result={"output_url": "file:///tmp/out.png"}))

    result = await provider.run(_image_job(job_id))
    await task

    gen = parse_result(result, "GENERATE_IMAGE")
    assert gen.success and _is_uuid(gen.media_id)


async def test_run_video_result_shape(test_db, provider):
    job_id = "jobvid123456"
    task = asyncio.ensure_future(_fake_worker(
        job_id, result={"output_url": "file:///tmp/out.mp4", "media_id": SAMPLE_UUID}))
    job = ProviderJob(job_id=job_id, kind=KIND_VIDEO, prompt="cat walks",
                      orientation="HORIZONTAL", start_url="file:///tmp/start.png")

    result = await provider.run(job)
    await task

    gen = parse_result(result, "GENERATE_VIDEO")
    assert gen.success
    assert gen.media_id == SAMPLE_UUID
    assert gen.url.endswith(".mp4")


async def test_run_propagates_worker_failure(test_db, provider):
    job_id = "jobfail12345"
    task = asyncio.ensure_future(_fake_worker(job_id, fail="boom"))
    result = await provider.run(_image_job(job_id))
    await task
    assert result.get("error") == "boom"


async def test_run_timeout_when_no_worker(test_db, provider):
    provider.timeout_s = 1
    provider.poll_s = 0.05
    result = await provider.run(_image_job("jobtimeout1"))
    assert "error" in result
    assert "timeout" in result["error"].lower()
    # the queued row is left behind for a later worker
    row = await crud.get_provider_job("jobtimeout1")
    assert row["status"] == "QUEUED"


async def test_run_validates_before_queuing(test_db, provider):
    # edit with no source: validation error, nothing queued
    job = ProviderJob(job_id="jobedit00001", kind=KIND_EDIT_IMAGE,
                      prompt="make it rain", orientation="VERTICAL")
    result = await provider.run(job)
    assert "error" in result and "No source image" in result["error"]
    assert await crud.get_provider_job("jobedit00001") is None

    # upscale is rejected by check()
    assert provider.check(ProviderJob(job_id="x", kind=KIND_UPSCALE)) is not None

    # unknown kind (dataclass rejects it at construction; mutate to reach the branch)
    weird = ProviderJob(job_id="jobunk000001", kind=KIND_IMAGE)
    weird.kind = "teleport"
    result = await provider.run(weird)
    assert "error" in result


async def test_run_video_requires_start_image(test_db, provider):
    job = ProviderJob(job_id="jobvidnoimg0", kind=KIND_VIDEO,
                      prompt="x", orientation="VERTICAL")
    result = await provider.run(job)
    assert "error" in result and "No vertical image" in result["error"]
    assert await crud.get_provider_job("jobvidnoimg0") is None


async def test_run_cancelled_job_reports_cancelled(test_db, provider):
    job_id = "jobcancel0001"

    async def canceller():
        for _ in range(200):
            if await crud.get_provider_job(job_id):
                break
            await asyncio.sleep(0.05)
        await crud.cancel_provider_job(job_id)

    task = asyncio.ensure_future(canceller())
    result = await provider.run(_image_job(job_id))
    await task
    assert "cancelled" in result["error"].lower()


async def test_register_existing_image_mints_uuid(test_db, provider, tmp_path):
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG fake")
    result = await provider.register_existing_image(f"file://{img}", name="pic")
    assert not result.get("error")
    mid = result["data"]["media"][0]["name"]
    assert _is_uuid(mid)
    assert result["data"]["url"].startswith("file://")
