import json
import re
from urllib.parse import urlencode

import pytest

from agent.services import flow_batch as fb
from agent.services.flow_payload_drift import (
    compare_and_record,
    payload_drift_status,
    reset_payload_drift_state,
)
from agent.services.flow_ui_generation import parse_generation_spec


PROJECT = "11111111-2222-3333-8444-555555555555"
MEDIA = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")


@pytest.fixture(autouse=True)
def _reset_state():
    reset_payload_drift_state()
    yield
    reset_payload_drift_state()


def _inner(freq: str):
    return json.loads(json.loads(freq)[0][0][1])


def _freq(rpcid: str, inner) -> str:
    return fb.build_envelope(rpcid, inner)


def _post(freq: str) -> str:
    return urlencode({"f.req": freq, "at": "never-inspected-secret"})


def _replace_volatile(value):
    if isinstance(value, str):
        if value == fb.CAPTCHA_SLOT:
            return "captcha-token-that-must-never-appear-" + "x" * 160
        if _UUID.fullmatch(value):
            return "12345678-1234-4abc-8def-1234567890ab"
        return value
    if isinstance(value, list):
        return [_replace_volatile(item) for item in value]
    return value


def test_image_volatile_values_and_multi_submit_do_not_report_drift():
    prompt = "private prompt should never be exposed"
    expected = fb.image_request(
        prompt,
        PROJECT,
        count=2,
        aspect="IMAGE_ASPECT_RATIO_LANDSCAPE",
        model="NARWHAL",
        ref_media_ids=[MEDIA],
    )
    actual_inner = _replace_volatile(_inner(expected))
    # UI launches x2 as separate ogiZ0b requests and chooses its own seed.
    actual_inner[1] = [actual_inner[1][0]]
    actual_inner[1][0][3] = 987654321
    actual = _freq(fb.RPC_GEN_IMAGE, actual_inner)

    report = compare_and_record(
        fb.RPC_GEN_IMAGE,
        expected,
        _post(actual),
        spec=parse_generation_spec(fb.RPC_GEN_IMAGE, expected),
    )

    assert report["detected"] is False
    assert report["expected_fingerprint"] == report["actual_fingerprint"]
    dumped = json.dumps(payload_drift_status())
    assert prompt not in dumped
    assert "captcha-token-that-must-never-appear" not in dumped
    assert MEDIA not in dumped
    assert PROJECT not in dumped


def test_first_frame_crop_change_is_detected():
    expected = fb.omni_first_frame_request(
        "move gently",
        PROJECT,
        MEDIA,
        duration_s=4,
        resolution="360p",
        aspect="VIDEO_ASPECT_RATIO_LANDSCAPE",
    )
    actual_inner = _replace_volatile(_inner(expected))
    actual_inner[0][0][4][5] = [None, 0.0038759689922481244, 1, 0.9961240310077519]

    report = compare_and_record(
        fb.RPC_GEN_VIDEO,
        expected,
        _post(_freq(fb.RPC_GEN_VIDEO, actual_inner)),
        spec=parse_generation_spec(fb.RPC_GEN_VIDEO, expected),
    )

    assert report["detected"] is True
    assert any("[4][5]" in diff["path"] for diff in report["differences"])
    assert payload_drift_status()["drift_events"] == 1


def test_text_video_descriptor_change_is_detected():
    expected = fb.text_video_request(
        "slow move",
        PROJECT,
        aspect="VIDEO_ASPECT_RATIO_LANDSCAPE",
        model="abra_t2v_4s",
        resolution="360p",
    )
    actual_inner = _replace_volatile(_inner(expected))
    actual_inner[2][1] = 1

    report = compare_and_record(
        fb.RPC_GEN_VIDEO_TEXT,
        expected,
        _post(_freq(fb.RPC_GEN_VIDEO_TEXT, actual_inner)),
        spec=parse_generation_spec(fb.RPC_GEN_VIDEO_TEXT, expected),
    )

    assert report["detected"] is True
    assert {diff["path"] for diff in report["differences"]} == {"$[2][1]"}


def test_text_video_resolution_slot_change_is_detected():
    expected = fb.text_video_request(
        "slow move",
        PROJECT,
        aspect="VIDEO_ASPECT_RATIO_LANDSCAPE",
        model="abra_t2v_4s",
        resolution="360p",
    )
    actual_inner = _replace_volatile(_inner(expected))
    actual_inner[0][0] = actual_inner[0][0][:-3]

    report = compare_and_record(
        fb.RPC_GEN_VIDEO_TEXT,
        expected,
        _post(_freq(fb.RPC_GEN_VIDEO_TEXT, actual_inner)),
        spec=parse_generation_spec(fb.RPC_GEN_VIDEO_TEXT, expected),
    )

    assert report["detected"] is True
    assert any(diff["path"].endswith(".length") for diff in report["differences"])
