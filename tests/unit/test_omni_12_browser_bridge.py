"""Merged PR #85 with the server's Playwright UI bridge."""
import pytest

from agent.services import flow_batch as fb
from agent.services.flow_ui_generation import (
    parse_generation_spec, _duration_from_model, _video_model_label
)
from agent.services.flow_playwright_generation import _validate_omni_12_credits
from agent.services.omni_model_versions import (
    is_omni_12_label, matches_model_label, estimate_omni_12_credits
)
from agent.services.omni_flash import omni12_model_key

PID="e3c606d7-adf3-48da-b4d1-92c2b3b1a604"


@pytest.mark.parametrize("duration",range(3,16))
def test_omni_12_t2v_spec_through_playwright_parser(duration):
    key=omni12_model_key("t2v",duration,"360p")
    request=fb.text_video_request("quiet lake",PID,model=key,resolution="360p")
    spec=parse_generation_spec(fb.RPC_GEN_VIDEO_TEXT,request)
    assert spec.model==key
    assert spec.kind=="text_video"
    assert spec.duration_s==duration
    assert spec.resolution=="360p"
    assert _video_model_label(spec.model)=="Omni 1.2 Flash"


@pytest.mark.parametrize("mode,expected",[
    ("t2v","macaron_cookie_t2v_3s"),
    ("first_frame","macaron_cookie_i2v_3s"),
    ("first_last","macaron_cookie_i2v_fl_3s"),
    ("r2v","macaron_cookie_r2v_3s"),
])
def test_omni_12_model_labels_in_all_modes(mode,expected):
    assert omni12_model_key(mode,3,"720p")==expected
    assert _duration_from_model(expected)==3
    assert _video_model_label(expected)=="Omni 1.2 Flash"


def test_aliases_are_version_exact():
    assert is_omni_12_label("Omni Flash 1.2")
    assert matches_model_label("Omni 1.2 Flash","Omni Flash 1.2")
    assert not matches_model_label("Omni 1.1 Flash","Omni 1.2 Flash")
    assert _video_model_label("abra_t2v_4s")=="Omni 1.1 Flash"


@pytest.mark.parametrize("seconds,resolution,price",[
    (3,"360p",3),(10,"360p",10),(11,"360p",12),(15,"360p",20),
    (3,"720p",9),(10,"720p",30),(11,"720p",36),(15,"720p",60),
])
def test_live_quote_budget(seconds,resolution,price):
    assert estimate_omni_12_credits(seconds,resolution)==price
    assert _validate_omni_12_credits(
        f"Для створення буде використано стільки кредитів: {price}",
        duration=seconds,resolution=resolution,cap=price
    )==price


def test_no_live_quote_fails_closed():
    with pytest.raises(RuntimeError,match="quote is unavailable"):
        _validate_omni_12_credits("Choose a duration", duration=3,resolution="360p",cap=3)


def test_price_above_guard_fails_without_submitting():
    with pytest.raises(RuntimeError,match="limit"):
        _validate_omni_12_credits(
            "Для створення буде використано стільки кредитів: 60",
            duration=15,resolution="720p",cap=20
        )


def test_live_quote_above_estimate_fails_without_submitting():
    with pytest.raises(RuntimeError,match="over configured limit"):
        _validate_omni_12_credits(
            "Для створення буде використано стільки кредитів: 90",
            duration=15,resolution="720p",cap=100
        )
