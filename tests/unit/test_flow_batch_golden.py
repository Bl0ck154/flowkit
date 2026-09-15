"""Byte-for-byte locks on the envelopes Flow actually accepts.

The tests in test_flow_batch.py assert *positions* — slot 3 is the seed, slot 5
is the model. These assert the *whole string*, because the refactor these guard
moves who calls the builder, and a payload Flow accepts and then quietly ignores
looks exactly like one that worked. Position assertions pass through a dropped
trailing null; a golden string does not.

If one of these fails, the question is never "update the golden". It is "did the
wire format change on purpose?" — and if it did, the new string belongs in
docs/CAPTURE.md with the capture that justifies it.

Every id in a request is a fresh uuid4, so the fixture pins uuid4 to a counter.
That is the only thing pinned: the builders are otherwise pure.
"""
import uuid as _uuid

import pytest

from agent.services import flow_batch as fb

PROJECT = "11111111-2222-3333-4444-555555555555"
MEDIA = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture
def pinned_uuids(monkeypatch):
    """uuid4 becomes a counter, so a built envelope is reproducible."""
    counter = iter(range(1, 999))
    monkeypatch.setattr(
        fb.uuid, "uuid4",
        lambda: _uuid.UUID(f"00000000-0000-4000-8000-{next(counter):012d}"),
    )


GOLDEN_IMAGE = (
    '[[["ogiZ0b","[null,[[null,null,[[\\"aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\\",null,'
    'null,null,1]],42,2,\\"GEM_PIX_2\\",null,[null,22,null,null,null,'
    '\\"11111111-2222-3333-4444-555555555555\\",null,null,null,null,'
    '[\\"__CAPTCHA__\\",1]],[[[\\"a cat\\"]]],null,null,null,'
    '\\"00000000-0000-4000-8000-000000000001\\",'
    '\\"00000000-0000-4000-8000-000000000002\\"]],1,[null,22,null,null,null,'
    '\\"11111111-2222-3333-4444-555555555555\\",null,null,null,null,'
    '[\\"__CAPTCHA__\\",1]],[\\"00000000-0000-4000-8000-000000000003\\"]]",'
    'null,"generic"]]]'
)

GOLDEN_VIDEO = (
    '[[["eb1hJf","[[[[null,null,[[[\\"a cat walks\\"]]]],'
    '\\"veo_3_1_i2v_lite_low_priority\\",1,null,[null,'
    '\\"aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\\",null,null,null,'
    '[null,0.0038759689922481244,1,0.9961240310077519]],'
    '[null,null,null,null,\\"00000000-0000-4000-8000-000000000001\\",'
    '\\"00000000-0000-4000-8000-000000000002\\"]]],[null,22,null,null,null,'
    '\\"11111111-2222-3333-4444-555555555555\\",null,null,null,null,'
    '[\\"__CAPTCHA__\\",1]],[\\"00000000-0000-4000-8000-000000000003\\",2]]",'
    'null,"generic"]]]'
)

GOLDEN_TEXT_VIDEO = (
    '[[["YhhmEf","[[[[null,null,[[[\\"a cat walks\\"]]]],\\"abra_t2v_8s\\",1,null,'
    '[null,null,null,null,\\"00000000-0000-4000-8000-000000000001\\",'
    '\\"00000000-0000-4000-8000-000000000002\\"]]],[null,22,null,null,null,'
    '\\"11111111-2222-3333-4444-555555555555\\",null,null,null,null,'
    '[\\"__CAPTCHA__\\",1]],[\\"00000000-0000-4000-8000-000000000003\\",1]]",'
    'null,"generic"]]]'
)


def test_image_request_envelope_is_unchanged(pinned_uuids):
    assert fb.image_request(
        "a cat", PROJECT, count=1, aspect="IMAGE_ASPECT_RATIO_PORTRAIT",
        seed=42, model="GEM_PIX_2", ref_media_ids=[MEDIA],
    ) == GOLDEN_IMAGE


def test_video_request_envelope_is_unchanged(pinned_uuids):
    """The i2v submit. This is the only video path running in production."""
    assert fb.video_request(
        "a cat walks", PROJECT, MEDIA, aspect="VIDEO_ASPECT_RATIO_PORTRAIT",
        model="veo_3_1_i2v_lite_low_priority",
    ) == GOLDEN_VIDEO


def test_text_video_request_envelope_is_unchanged(pinned_uuids):
    assert fb.text_video_request(
        "a cat walks", PROJECT, aspect="VIDEO_ASPECT_RATIO_PORTRAIT",
        model="abra_t2v_8s",
    ) == GOLDEN_TEXT_VIDEO


def test_video_request_passes_the_model_key_through_untouched(pinned_uuids):
    """Omni rides the same rpc as Veo, differing only by this string.

    video_request does NOT call resolve_video_model — the caller decides. That
    is what lets one submit serve both families, so it is worth a test of its
    own rather than being implied by the golden above.
    """
    freq = fb.video_request("x", PROJECT, MEDIA, model="abra_i2v_8s")
    assert '\\"abra_i2v_8s\\"' in freq
    assert "veo_3_1" not in freq
