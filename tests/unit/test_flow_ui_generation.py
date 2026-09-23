import json

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
