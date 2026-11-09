import asyncio
import json

import pytest

from agent.services import remote_flow_worker as rw
from agent.services.flow_ui_generation import UIGenerationSpec


class FakeWorker:
    def __init__(self):
        self.sent = []
        self.closed = False

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def close(self, **_kwargs):
        self.closed = True


@pytest.mark.asyncio
async def test_remote_worker_round_trip(monkeypatch):
    worker = FakeWorker()
    await rw.set_worker(worker)
    monkeypatch.setattr(
        rw,
        "parse_generation_spec",
        lambda _rpcid, _freq: UIGenerationSpec(
            rpcid="ogiZ0b",
            project_id="project-1",
            kind="image",
            prompt="hello",
            aspect=1,
            model="NARWHAL",
            count=1,
        ),
    )
    monkeypatch.setattr(rw, "_picker_tokens", lambda *_args, **_kwargs: asyncio.sleep(0, result={}))

    task = asyncio.create_task(
        rw.run_remote_ui_generation("ogiZ0b", "ignored", project_id="project-1", timeout=1)
    )
    for _ in range(20):
        if worker.sent:
            break
        await asyncio.sleep(0)
    assert worker.sent
    job = worker.sent[0]
    assert job["method"] == "ui_generate"
    assert job["params"]["spec"]["prompt"] == "hello"

    await rw.handle_message(
        {"id": job["id"], "result": {"status": 200, "data": "flow-response"}},
        worker,
    )
    assert await task == {"status": 200, "data": "flow-response"}
    rw.clear_worker(worker)


@pytest.mark.asyncio
async def test_remote_worker_disconnect_resolves_pending(monkeypatch):
    worker = FakeWorker()
    await rw.set_worker(worker)
    monkeypatch.setattr(
        rw,
        "parse_generation_spec",
        lambda _rpcid, _freq: UIGenerationSpec(
            rpcid="ogiZ0b",
            project_id="project-1",
            kind="image",
            prompt="hello",
            aspect=1,
            model="NARWHAL",
            count=1,
        ),
    )
    monkeypatch.setattr(rw, "_picker_tokens", lambda *_args, **_kwargs: asyncio.sleep(0, result={}))

    task = asyncio.create_task(
        rw.run_remote_ui_generation("ogiZ0b", "ignored", project_id="project-1", timeout=1)
    )
    for _ in range(20):
        if worker.sent:
            break
        await asyncio.sleep(0)
    rw.clear_worker(worker)
    result = await task
    assert result["status"] == 503
    assert result["error"] == "REMOTE_FLOW_WORKER_DISCONNECTED"


@pytest.mark.asyncio
async def test_remote_batch_rpc_round_trip():
    worker = FakeWorker()
    await rw.set_worker(worker)

    task = asyncio.create_task(
        rw.run_remote_batch_rpc("rpc-1", "freq-payload", timeout=1)
    )
    for _ in range(20):
        if worker.sent:
            break
        await asyncio.sleep(0)
    assert worker.sent
    job = worker.sent[0]
    assert job["method"] == "batch_rpc"
    assert job["params"]["rpcid"] == "rpc-1"
    assert job["params"]["freq"] == "freq-payload"

    await rw.handle_message(
        {"id": job["id"], "status": 200, "data": "batch-response"},
        worker,
    )
    assert await task == {"status": 200, "data": "batch-response"}
    rw.clear_worker(worker)
