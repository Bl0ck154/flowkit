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
