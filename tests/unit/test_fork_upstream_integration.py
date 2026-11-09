"""Guard against silent breakage when upstream and fork APIs are merged."""

from agent.main import app
from agent.services import flow_batch as fb
from agent.services.flow_client import FlowClient


def test_fastapi_registers_fork_and_upstream_routes():
    # The current FastAPI may lazily expand included routers; inspect OpenAPI
    # instead of iterating app.routes directly.
    paths = set(app.openapi()["paths"])
    assert {
        "/health",
        "/api/flow/credits",
        "/api/flow/upscale-video",
        "/api/flow/export-video",
        "/api/flow/check-export-status",
        "/api/providers/status",
    } <= paths


def test_native_1080p_export_contract_is_still_exposed():
    assert fb.RPC_UPSCALE == "p0UkFb"
    assert callable(fb.upscale_request)
    assert callable(fb.read_upscaled_media_id)


def test_flow_client_retains_fork_cooldown_metadata():
    c = FlowClient()
    status = c.generation_guard_status
    assert "cooldown_reason" in status
    assert hasattr(c, "_batch_active_project")
