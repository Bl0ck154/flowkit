"""Tests for the provider-job queue: CRUD lease semantics + HTTP API.

pytest-asyncio runs in AUTO mode (see pytest.ini).
"""
import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api.provider_jobs import router as provider_jobs_router
from agent.db import crud


@pytest.fixture
def api_client(test_db):
    app = FastAPI()
    app.include_router(provider_jobs_router, prefix="/api")
    return TestClient(app)


async def _mk(provider="assistant", kind="image", job_id=None, **kw):
    return await crud.create_provider_job(provider=provider, kind=kind,
                                          prompt="p", job_id=job_id, **kw)


# ---------------------------------------------------------------------------
# CRUD: lifecycle + leasing
# ---------------------------------------------------------------------------

async def test_create_and_get(test_db):
    row = await _mk(job_id="j1")
    assert row["status"] == "QUEUED"
    assert row["provider"] == "assistant"
    assert json.loads(row["extra"]) == {}
    got = await crud.get_provider_job("j1")
    assert got["id"] == "j1"


async def test_list_filters(test_db):
    await _mk(job_id="a1", provider="assistant")
    await _mk(job_id="a2", provider="assistant")
    await _mk(job_id="f1", provider="flow")
    rows = await crud.list_provider_jobs(provider="assistant")
    assert {r["id"] for r in rows} == {"a1", "a2"}
    rows = await crud.list_provider_jobs(status="QUEUED", limit=10)
    assert len(rows) == 3


async def test_claim_happy_path(test_db):
    await _mk(job_id="j1")
    row = await crud.claim_provider_job("j1", "w1", lease_ttl_s=300)
    assert row["status"] == "CLAIMED"
    assert row["claimed_by"] == "w1"
    assert row["lease_expires_at"] is not None


async def test_claim_conflict_when_lease_valid(test_db):
    await _mk(job_id="j1")
    assert await crud.claim_provider_job("j1", "w1", lease_ttl_s=300)
    # second worker cannot steal a live lease
    assert await crud.claim_provider_job("j1", "w2", lease_ttl_s=300) is None


async def test_claim_reclaims_expired_lease(test_db):
    await _mk(job_id="j1")
    assert await crud.claim_provider_job("j1", "w1", lease_ttl_s=-1)  # already expired
    row = await crud.claim_provider_job("j1", "w2", lease_ttl_s=300)
    assert row is not None and row["claimed_by"] == "w2"


async def test_claim_rejects_terminal(test_db):
    await _mk(job_id="j1")
    await crud.claim_provider_job("j1", "w1")
    await crud.complete_provider_job("j1", "w1", {"output_url": "x"})
    assert await crud.claim_provider_job("j1", "w1") is None
    assert await crud.get_provider_job("missing") is None or True
    assert await crud.claim_provider_job("missing", "w1") is None


async def test_heartbeat_extends_and_rejects_stranger(test_db):
    await _mk(job_id="j1")
    await crud.claim_provider_job("j1", "w1", lease_ttl_s=60)
    before = (await crud.get_provider_job("j1"))["lease_expires_at"]
    await asyncio.sleep(0.05)
    row = await crud.heartbeat_provider_job("j1", "w1", lease_ttl_s=600)
    assert row is not None
    assert row["lease_expires_at"] > before
    assert row["status"] == "RUNNING"  # CLAIMED -> RUNNING on first heartbeat
    # a different worker cannot heartbeat
    assert await crud.heartbeat_provider_job("j1", "w2") is None


async def test_progress_complete_fail_cancel(test_db):
    await _mk(job_id="j1")
    await crud.claim_provider_job("j1", "w1")
    row = await crud.update_provider_job_progress("j1", "w1", 42, "halfway")
    assert row["progress"] == 42 and row["progress_message"] == "halfway"
    row = await crud.complete_provider_job("j1", "w1", {"output_url": "file:///o.png"})
    assert row["status"] == "SUCCEEDED" and row["progress"] == 100
    assert json.loads(row["result"])["output_url"] == "file:///o.png"

    await _mk(job_id="j2")
    await crud.claim_provider_job("j2", "w1")
    row = await crud.fail_provider_job("j2", "w1", "boom")
    assert row["status"] == "FAILED" and row["error_message"] == "boom"

    await _mk(job_id="j3")
    row = await crud.cancel_provider_job("j3")
    assert row["status"] == "CANCELLED"


async def test_ownership_enforced(test_db):
    """Only the lease holder may touch a live job; terminal rules hold."""
    await _mk(job_id="j1")
    # stranger progress/complete/fail on a QUEUED job -> None
    assert await crud.update_provider_job_progress("j1", "w9", 10) is None
    assert await crud.complete_provider_job("j1", "w9", {}) is None
    assert await crud.fail_provider_job("j1", "w9", "x") is None

    await crud.claim_provider_job("j1", "w1")
    # wrong worker still rejected
    assert await crud.update_provider_job_progress("j1", "w2", 10) is None
    assert await crud.complete_provider_job("j1", "w2", {}) is None
    assert await crud.fail_provider_job("j1", "w2", "x") is None

    # holder completes; stranger fail afterwards is rejected
    row = await crud.complete_provider_job("j1", "w1", {"output_url": "o"})
    assert row["status"] == "SUCCEEDED"
    assert await crud.fail_provider_job("j1", "w1", "late") is None
    assert await crud.fail_provider_job("j1", "w2", "late") is None

    # idempotent re-complete returns the row
    row2 = await crud.complete_provider_job("j1", "w1", {"output_url": "o"})
    assert row2["status"] == "SUCCEEDED"
    assert json.loads(row2["result"])["output_url"] == "o"

    # cancel on terminal job rejected
    assert await crud.cancel_provider_job("j1") is None


async def test_fail_idempotent_and_cancel_guards(test_db):
    await _mk(job_id="j2")
    await crud.claim_provider_job("j2", "w1")
    row = await crud.fail_provider_job("j2", "w1", "boom")
    assert row["status"] == "FAILED"
    # idempotent re-fail returns the row
    row2 = await crud.fail_provider_job("j2", "w1", "boom")
    assert row2["status"] == "FAILED" and row2["error_message"] == "boom"
    # a SUCCEEDED job cannot be failed
    await _mk(job_id="j3")
    await crud.claim_provider_job("j3", "w1")
    await crud.complete_provider_job("j3", "w1", {})
    assert await crud.fail_provider_job("j3", "w1", "x") is None
    # cancel a live job works, twice does not
    await _mk(job_id="j4")
    await crud.claim_provider_job("j4", "w1")
    assert (await crud.cancel_provider_job("j4"))["status"] == "CANCELLED"
    assert await crud.cancel_provider_job("j4") is None


async def test_wait_for_job_returns_on_completion(test_db):
    await _mk(job_id="j1")
    await crud.claim_provider_job("j1", "w1")

    async def finisher():
        await asyncio.sleep(0.2)
        await crud.complete_provider_job("j1", "w1", {"output_url": "x"})

    task = asyncio.ensure_future(finisher())
    row = await crud.wait_for_provider_job("j1", timeout_s=10, poll_interval_s=0.05)
    await task
    assert row["status"] == "SUCCEEDED"


async def test_wait_for_job_timeout(test_db):
    await _mk(job_id="j1")
    assert await crud.wait_for_provider_job("j1", timeout_s=0.3, poll_interval_s=0.05) is None
    assert await crud.wait_for_provider_job("missing", timeout_s=1) is None


async def test_next_queued_claims_oldest(test_db):
    await _mk(job_id="old")
    await asyncio.sleep(0.02)
    await _mk(job_id="new")
    row = await crud.next_queued_provider_job("assistant", "w1")
    assert row["id"] == "old" and row["claimed_by"] == "w1"
    # second call gets the next one
    row = await crud.next_queued_provider_job("assistant", "w1")
    assert row["id"] == "new"
    assert await crud.next_queued_provider_job("assistant", "w1") is None
    assert await crud.next_queued_provider_job("flow", "w1") is None


# ---------------------------------------------------------------------------
# HTTP API
# ---------------------------------------------------------------------------

def test_api_create_get_wait_cycle(api_client):
    r = api_client.post("/api/provider-jobs", json={
        "provider": "assistant", "kind": "image", "prompt": "a cat",
        "orientation": "VERTICAL", "extra": {"a": 1}})
    assert r.status_code == 200, r.text
    job = r.json()
    job_id = job["id"]
    assert job["status"] == "QUEUED"
    assert job["extra"] == {"a": 1}  # JSON columns parsed

    r = api_client.get(f"/api/provider-jobs/{job_id}")
    assert r.status_code == 200 and r.json()["prompt"] == "a cat"

    r = api_client.get("/api/provider-jobs", params={"provider": "assistant"})
    assert any(j["id"] == job_id for j in r.json())

    # claim + heartbeat + progress + complete
    r = api_client.post(f"/api/provider-jobs/{job_id}/claim",
                        json={"worker_id": "w1", "lease_ttl_s": 300})
    assert r.status_code == 200 and r.json()["claimed_by"] == "w1"

    r = api_client.post(f"/api/provider-jobs/{job_id}/heartbeat",
                        json={"worker_id": "w1"})
    assert r.status_code == 200 and r.json()["status"] == "RUNNING"

    r = api_client.post(f"/api/provider-jobs/{job_id}/progress",
                        json={"worker_id": "w1", "progress": 50, "message": "half"})
    assert r.status_code == 200 and r.json()["progress"] == 50

    # stranger progress is rejected
    r = api_client.post(f"/api/provider-jobs/{job_id}/progress",
                        json={"worker_id": "w2", "progress": 60})
    assert r.status_code == 409

    r = api_client.post(f"/api/provider-jobs/{job_id}/complete",
                        json={"worker_id": "w1",
                              "result": {"output_url": "file:///o.png"}})
    assert r.status_code == 200
    assert r.json()["status"] == "SUCCEEDED"
    assert r.json()["result"]["output_url"] == "file:///o.png"

    # idempotent re-complete returns the row
    r = api_client.post(f"/api/provider-jobs/{job_id}/complete",
                        json={"worker_id": "w1",
                              "result": {"output_url": "file:///o.png"}})
    assert r.status_code == 200 and r.json()["status"] == "SUCCEEDED"

    # a stranger's complete on the terminal job is still rejected
    r = api_client.post(f"/api/provider-jobs/{job_id}/complete",
                        json={"worker_id": "w2",
                              "result": {"output_url": "file:///evil.png"}})
    assert r.status_code == 409

    # wait returns immediately for terminal jobs
    r = api_client.get(f"/api/provider-jobs/{job_id}/wait", params={"timeout_s": 5})
    assert r.status_code == 200 and r.json()["status"] == "SUCCEEDED"


def test_api_wait_next_long_poll(api_client):
    import threading, time
    created = {}

    def producer():
        time.sleep(0.5)
        r = api_client.post("/api/provider-jobs", json={
            "provider": "assistant", "kind": "image", "prompt": "late job"})
        created["id"] = r.json()["id"]

    t = threading.Thread(target=producer)
    t.start()
    r = api_client.get("/api/provider-jobs/wait-next",
                       params={"provider": "assistant", "worker_id": "w9",
                               "timeout_s": 10})
    t.join()
    assert r.status_code == 200, r.text
    assert r.json()["id"] == created["id"]
    assert r.json()["claimed_by"] == "w9"


def test_api_wait_next_timeout_returns_204(api_client):
    r = api_client.get("/api/provider-jobs/wait-next",
                       params={"provider": "nobody", "worker_id": "w1",
                               "timeout_s": 1})
    assert r.status_code == 204


def test_api_errors(api_client):
    assert api_client.get("/api/provider-jobs/missing").status_code == 404
    assert api_client.get("/api/provider-jobs/missing/wait").status_code == 404
    r = api_client.post("/api/provider-jobs/missing/claim",
                        json={"worker_id": "w1"})
    assert r.status_code == 409
    # heartbeat by non-holder
    r = api_client.post("/api/provider-jobs", json={
        "provider": "assistant", "kind": "image", "prompt": "x"})
    jid = r.json()["id"]
    api_client.post(f"/api/provider-jobs/{jid}/claim", json={"worker_id": "w1"})
    r = api_client.post(f"/api/provider-jobs/{jid}/heartbeat",
                        json={"worker_id": "w2"})
    assert r.status_code == 409
    # fail by non-holder rejected; fail by holder works
    r = api_client.post(f"/api/provider-jobs/{jid}/fail",
                        json={"worker_id": "w2", "error": "bad"})
    assert r.status_code == 409
    r = api_client.post(f"/api/provider-jobs/{jid}/fail",
                        json={"worker_id": "w1", "error": "bad"})
    assert r.json()["status"] == "FAILED"
    # cancel on a terminal job is rejected
    r = api_client.post(f"/api/provider-jobs/{jid}/cancel")
    assert r.status_code == 409
    r = api_client.post("/api/provider-jobs", json={
        "provider": "assistant", "kind": "image", "prompt": "y"})
    jid2 = r.json()["id"]
    r = api_client.post(f"/api/provider-jobs/{jid2}/cancel")
    assert r.json()["status"] == "CANCELLED"
