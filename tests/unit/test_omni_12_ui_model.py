"""Omni 1.2 aliases, durations and no-spend early validation."""
from unittest.mock import AsyncMock
import pytest
from agent.services import omni_flash
from agent.services import flow_batch as fb
from agent.services.omni_model_versions import (
    is_omni_12_label, matches_model_label, estimate_omni_12_credits,
    OMNI_12_DURATIONS,
)
from agent.services.flow_ui_generation import _duration_from_model, _video_model_label


def test_omni_12_names_never_alias_omni_11():
    assert is_omni_12_label("Omni 1.2 Flash")
    assert is_omni_12_label("Gemini Omni Flash 1.2")
    assert matches_model_label("Omni Flash 1.2", "Omni 1.2 Flash")
    assert not matches_model_label("Omni 1.1 Flash", "Omni Flash 1.2")
    assert not is_omni_12_label("Omni 1.1 Flash")


@pytest.mark.parametrize("duration", range(3, 16))
def test_all_omni_12_durations_parse_without_guessing_wire_keys(duration):
    assert duration in OMNI_12_DURATIONS
    model=f"omni_1_2_t2v_{duration}s_360p"
    assert _duration_from_model(model)==duration
    assert _video_model_label(model)=="Omni 1.2 Flash"


@pytest.mark.parametrize("seconds,low,high", [
    (3, 3, 9), (10, 10, 30), (11, 12, 36), (15, 20, 60),
])
def test_published_credit_tiers(seconds, low, high):
    assert estimate_omni_12_credits(seconds, "360p")==low
    assert estimate_omni_12_credits(seconds, "720p")==high


def test_out_of_range_is_rejected():
    with pytest.raises(ValueError):
        estimate_omni_12_credits(16, "720p")
    with pytest.raises(ValueError):
        estimate_omni_12_credits(2, "360p")


@pytest.mark.asyncio
async def test_no_omni_12_on_unverified_extension_path(monkeypatch):
    monkeypatch.setattr(omni_flash._config, "FLOW_BROWSER_BACKEND", "extension")
    result=await omni_flash.generate_omni_flash_text_video(
        prompt="test",project_id="project-uuid",model_version="1.2",duration_s=3,
        resolution="360p")
    assert result["status"]==422
    assert "unverified extension batch model ids" in result["error"]


@pytest.mark.asyncio
async def test_credit_guard_prevents_generation(monkeypatch):
    monkeypatch.setattr(omni_flash._config, "FLOW_BROWSER_BACKEND", "playwright_ui")
    from agent.services import remote_flow_worker
    monkeypatch.setattr(remote_flow_worker, "connected", lambda: False)
    result=await omni_flash.generate_omni_flash_text_video(
        prompt="test",project_id="project-uuid",model_version="1.2",duration_s=15,
        resolution="720p",max_credits=20)
    assert result["status"]==422
    assert "60" in result["error"]


@pytest.mark.asyncio
async def test_omni_12_creates_only_a_ui_marker(monkeypatch):
    monkeypatch.setattr(omni_flash._config, "FLOW_BROWSER_BACKEND", "playwright_ui")
    from agent.services import remote_flow_worker
    monkeypatch.setattr(remote_flow_worker, "connected",lambda: False)
    class Client:
        def _batch_project_id(self, project_id):return project_id
        async def _batch_payload(self,rpcid,freq,*args,**kwargs):
            assert rpcid==fb.RPC_GEN_VIDEO_TEXT
            assert 'omni_1_2_t2v_3s_360p' in freq
            return ["placeholder"]
    monkeypatch.setattr(omni_flash, "get_flow_client", lambda: Client())
    monkeypatch.setattr(fb, "read_text_video_submit",
        lambda payload: {"media_id":"test-media","workflow_id":"test-workflow"})
    result=await omni_flash.generate_omni_flash_text_video(
        prompt="test",project_id="test-project",model_version="1.2",duration_s=3,
        resolution="360p",max_credits=3)
    assert result["status"]==200
    assert result["data"]["model_version"]=="1.2"
