import asyncio
from types import SimpleNamespace
import pytest

from agent.services.flow_playwright_generation import _capture_generation_response


@pytest.mark.asyncio
async def test_capture_generation_route_retains_body_before_navigation():
    events = []
    class Response:
        status = 200
        async def text(self):
            events.append("read_before_navigation")
            return "video-submit-response"
    class Route:
        def __init__(self):
            self.request=SimpleNamespace(post_data="f.req=payload")
        async def fetch(self, **kwargs):
            events.append("forward_exactly_once")
            return Response()
        async def fulfill(self, **kwargs):
            events.append("fulfill_to_frontend")
        async def abort(self):
            events.append("abort")
    future=asyncio.get_running_loop().create_future()
    await _capture_generation_response(Route(), future, 120)
    assert await future==(200, "video-submit-response", "f.req=payload")
    assert events==["forward_exactly_once","read_before_navigation","fulfill_to_frontend"]


@pytest.mark.asyncio
async def test_capture_failure_does_not_resubmit():
    events=[]
    class Route:
        request=SimpleNamespace(post_data="f.req=payload")
        async def fetch(self, **kwargs):
            events.append("fetch_once")
            raise RuntimeError("upstream cancelled")
        async def abort(self):
            events.append("abort")
    future=asyncio.get_running_loop().create_future()
    await _capture_generation_response(Route(),future,120)
    with pytest.raises(RuntimeError,match="upstream cancelled"):
        await future
    assert events==["fetch_once","abort"]

@pytest.mark.asyncio
async def test_radio_waits_for_async_model_options_before_click():
    from agent.services.flow_playwright_generation import _click_radio_text

    class Item:
        clicked = 0
        async def inner_text(self):
            return "720p"
        async def get_attribute(self, name):
            return "false" if name == "aria-checked" else None
        async def click(self):
            self.clicked += 1

    class Page:
        def __init__(self):
            self.counts = 0
            self.waits = []
            self.item = Item()
        def locator(self, selector):
            assert selector == 'button[role="radio"]:visible'
            return self
        async def count(self):
            self.counts += 1
            return 1 if self.counts >= 3 else 0
        def nth(self, index):
            assert index == 0
            return self.item
        async def wait_for_timeout(self, ms):
            self.waits.append(ms)

    page = Page()
    await _click_radio_text(page, "720p")
    assert page.counts == 3
    assert page.item.clicked == 1
    assert page.waits == [400, 400, 200]


@pytest.mark.asyncio
async def test_missing_radio_fails_closed_without_click_or_generate():
    from agent.services.flow_playwright_generation import _click_radio_text

    class Page:
        def __init__(self):
            self.polls = 0
            self.waits = []
        def locator(self, selector):
            assert selector == 'button[role="radio"]:visible'
            return self
        async def count(self):
            self.polls += 1
            return 0
        async def wait_for_timeout(self, ms):
            self.waits.append(ms)

    page = Page()
    with pytest.raises(RuntimeError, match="Flow UI radio not found: 720p"):
        await _click_radio_text(page, "720p")
    assert page.polls == 9
    assert page.waits == [400] * 8
