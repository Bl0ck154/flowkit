import json

import pytest

from agent.services import flow_batch as fb
from agent.services.flow_ui_generation import parse_generation_spec


PROJECT = "11111111-2222-3333-4444-555555555555"
START = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
END = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REF2 = "cccccccc-dddd-eeee-ffff-000000000000"


def test_parse_image_generation_spec():
    freq = fb.image_request(
        "draw a mug",
        PROJECT,
        count=2,
        aspect="IMAGE_ASPECT_RATIO_LANDSCAPE",
        model="NARWHAL",
        ref_media_ids=[START],
    )
    spec = parse_generation_spec(fb.RPC_GEN_IMAGE, freq)
    assert spec.kind == "image"
    assert spec.project_id == PROJECT
    assert spec.prompt == "draw a mug"
    assert spec.aspect == fb.ASPECT_LANDSCAPE
    assert spec.model == "NARWHAL"
    assert spec.count == 2
    assert spec.reference_media_ids == [START]


def test_parse_text_video_spec():
    freq = fb.text_video_request(
        "slow camera move",
        PROJECT,
        aspect="VIDEO_ASPECT_RATIO_PORTRAIT",
        model="abra_t2v_8s_360p",
    )
    spec = parse_generation_spec(fb.RPC_GEN_VIDEO_TEXT, freq)
    assert spec.kind == "text_video"
    assert spec.duration_s == 8
    assert spec.resolution == "360p"
    assert spec.aspect == fb.VIDEO_ASPECT_PORTRAIT


def test_parse_first_frame_spec():
    freq = fb.omni_first_frame_request(
        "animate gently",
        PROJECT,
        START,
        duration_s=6,
        resolution="360p",
        aspect="VIDEO_ASPECT_RATIO_LANDSCAPE",
    )
    spec = parse_generation_spec(fb.RPC_GEN_VIDEO, freq)
    assert spec.kind == "first_frame"
    assert spec.start_media_id == START
    assert spec.duration_s == 6
    assert spec.resolution == "360p"


def test_parse_first_last_spec():
    freq = fb.omni_first_last_request(
        "move between frames",
        PROJECT,
        START,
        END,
        duration_s=10,
        resolution="720p",
    )
    spec = parse_generation_spec(fb.RPC_GEN_VIDEO_FIRST_LAST, freq)
    assert spec.kind == "first_last"
    assert spec.start_media_id == START
    assert spec.end_media_id == END
    assert spec.duration_s == 10
    assert spec.resolution == "720p"


def test_parse_reference_video_spec():
    freq = fb.omni_reference_video_request(
        "keep the same characters",
        PROJECT,
        [START, REF2],
        duration_s=4,
        resolution="360p",
    )
    spec = parse_generation_spec(fb.RPC_GEN_VIDEO_REFERENCES, freq)
    assert spec.kind == "references"
    assert spec.reference_media_ids == [START, REF2]
    assert spec.duration_s == 4
    assert spec.resolution == "360p"


@pytest.mark.asyncio
async def test_picker_asb_url_uses_last_media_record(monkeypatch):
    media_id = START
    asb_url = "https://lh3.googleusercontent.com/asb/OPAQUE_PICKER_TOKEN"
    calls = []

    async def fake_batch_rpc(rpcid, freq, **kwargs):
        calls.append((rpcid, freq, kwargs))
        return {"status": 200, "data": media_id + '\\\",null,[[123],null,null,null,null,\\\"' + asb_url + '\\\"'}

    monkeypatch.setattr("agent.services.flow_ui_generation.bs.run_flow_batch_rpc", fake_batch_rpc)
    from agent.services.flow_ui_generation import _picker_asb_url

    assert await _picker_asb_url(PROJECT, media_id) == asb_url
    assert calls[0][0] == fb.RPC_PROJECT_MEDIA
    assert calls[0][2]["match"] == media_id
    assert calls[0][2]["match_last"] is True
    assert calls[0][2]["project_id"] == PROJECT


def test_find_picker_asb_url_from_listing_window():
    asb_url = "https://lh3.googleusercontent.com/asb/AB-nOU_example_token"
    raw = (
        START
        + '\\\",\\\"' + PROJECT + '\\\",\\\"asset-id\\\",\\\"CAE\\\",null,'
        + '[[123],null,null,null,null,\\\"' + asb_url + '\\\",[null,null,null,null,1]]'
    )
    assert fb.find_picker_asb_url_in_text(raw, START) == asb_url


@pytest.mark.asyncio
async def test_configure_ui_reloads_once_when_picker_cache_is_stale(monkeypatch):
    from agent.services import flow_ui_generation as ui

    calls = []
    attempts = 0

    class FakeCDP:
        async def command(self, method, params=None, timeout=15):
            calls.append((method, params or {}))
            return {}

    async def fake_once(cdp, spec):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ui.PickerMediaNotFound(START)

    async def fake_wait(cdp, timeout=15):
        calls.append(("wait-ui", {}))

    async def fake_sleep(_):
        return None

    monkeypatch.setattr(ui, "_configure_ui_once", fake_once)
    monkeypatch.setattr(ui, "_wait_for_ui", fake_wait)
    monkeypatch.setattr(ui.asyncio, "sleep", fake_sleep)

    spec = ui.UIGenerationSpec(
        rpcid=fb.RPC_GEN_VIDEO,
        project_id=PROJECT,
        kind="first_frame",
        prompt="move gently",
        aspect=fb.VIDEO_ASPECT_LANDSCAPE,
        model="abra_i2v_10s",
        duration_s=10,
        resolution="720p",
        start_media_id=START,
    )
    await ui._configure_ui(FakeCDP(), spec)

    assert attempts == 2
    assert calls == [("Page.reload", {"ignoreCache": True}), ("wait-ui", {})]


def test_fresh_upload_marker_is_consumed_only_for_referenced_media():
    from agent.services import flow_ui_generation as ui

    ui._fresh_uploaded_media.clear()
    ui.mark_uploaded_media_for_ui_refresh(PROJECT, START)
    other = ui.UIGenerationSpec(
        rpcid=fb.RPC_GEN_VIDEO,
        project_id=PROJECT,
        kind="first_frame",
        prompt="x",
        aspect=fb.VIDEO_ASPECT_LANDSCAPE,
        model="abra_i2v_10s",
        start_media_id=END,
    )
    wanted = ui.UIGenerationSpec(
        rpcid=fb.RPC_GEN_VIDEO,
        project_id=PROJECT,
        kind="first_frame",
        prompt="x",
        aspect=fb.VIDEO_ASPECT_LANDSCAPE,
        model="abra_i2v_10s",
        start_media_id=START,
    )

    assert ui._consume_fresh_media_refresh(other) is False
    assert ui._consume_fresh_media_refresh(wanted) is True
    assert ui._consume_fresh_media_refresh(wanted) is False
