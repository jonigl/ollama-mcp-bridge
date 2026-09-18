"""Tests for aborting the upstream request when the client disconnects (issue #69)"""

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.responses import StreamingResponse

try:
    from ollama_mcp_bridge import api
    from ollama_mcp_bridge.utils import ClientDisconnected, run_until_client_disconnects
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from ollama_mcp_bridge import api
    from ollama_mcp_bridge.utils import ClientDisconnected, run_until_client_disconnects


class FakeChannel:
    """ASGI receive channel: serves queued messages, then blocks until marked disconnected.

    It must block rather than return nothing: ``is_disconnected`` polls inside a cancelled
    scope, so a channel with no message available must not hand one back.
    """

    def __init__(self, messages=()):
        self.messages = list(messages)
        self.disconnected = False
        self.polls = 0

    async def __call__(self):
        self.polls += 1
        if self.messages:
            return self.messages.pop(0)
        if self.disconnected:
            return {"type": "http.disconnect"}
        await asyncio.Event().wait()


class ConnectedRequest:
    """A request whose client never leaves."""

    async def is_disconnected(self):
        return False


def make_request(path, channel):
    return Request({"type": "http", "method": "POST", "path": path, "headers": []}, channel)


@pytest.mark.anyio
async def test_run_until_client_disconnects_returns_result_of_the_work():
    """The work wins the race, so its result comes back untouched."""

    async def work():
        await asyncio.sleep(0)
        return {"message": {"content": "hi"}}

    assert await run_until_client_disconnects(work(), ConnectedRequest()) == {"message": {"content": "hi"}}


@pytest.mark.anyio
async def test_run_until_client_disconnects_propagates_errors_from_the_work():
    """A failing call must still raise, not be masked by the watcher."""

    async def work():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await run_until_client_disconnects(work(), ConnectedRequest())


@pytest.mark.anyio
async def test_run_until_client_disconnects_cancels_the_work_when_the_client_leaves():
    """The watcher wins, so the in-flight work is cancelled."""
    started = asyncio.Event()
    state = {"cancelled": False}

    async def work():
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            state["cancelled"] = True
            raise

    channel = FakeChannel()
    request = make_request("/api/chat", channel)

    race = asyncio.ensure_future(run_until_client_disconnects(work(), request, poll_interval=0.01))
    await started.wait()
    channel.disconnected = True

    with pytest.raises(ClientDisconnected):
        await asyncio.wait_for(race, timeout=2)
    assert state["cancelled"]


@pytest.mark.anyio
async def test_chat_aborts_the_ollama_request_when_the_client_disconnects(monkeypatch):
    """Non-streaming /api/chat must stop driving Ollama once the client is gone."""
    started = asyncio.Event()
    state = {"cancelled": False}

    class StubProxyService:
        async def proxy_chat_with_tools(self, payload, stream=False):
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                state["cancelled"] = True
                raise

    monkeypatch.setattr(api, "get_proxy_service", lambda: StubProxyService())

    channel = FakeChannel()
    request = make_request("/api/chat", channel)

    task = asyncio.ensure_future(api.chat(request, {"messages": [{"role": "user", "content": "hi"}]}))
    await started.wait()
    channel.disconnected = True

    response = await asyncio.wait_for(task, timeout=2)
    assert response.status_code == api.CLIENT_CLOSED_REQUEST
    assert state["cancelled"]


@pytest.mark.anyio
async def test_generic_proxy_aborts_and_still_reads_the_body(monkeypatch):
    """The catch-all buffers too, and its body must survive the watcher."""
    started = asyncio.Event()
    state = {"cancelled": False, "body": None}

    class StubProxyService:
        async def proxy_generic_request(self, path, request):
            state["body"] = await request.body()
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                state["cancelled"] = True
                raise

    monkeypatch.setattr(api, "get_proxy_service", lambda: StubProxyService())

    channel = FakeChannel([{"type": "http.request", "body": b'{"model": "qwen3"}', "more_body": False}])
    request = make_request("/api/generate", channel)

    task = asyncio.ensure_future(api.proxy_to_ollama(request, "api/generate"))
    await started.wait()
    channel.disconnected = True

    response = await asyncio.wait_for(task, timeout=2)
    assert response.status_code == api.CLIENT_CLOSED_REQUEST
    assert state["cancelled"]
    assert state["body"] == b'{"model": "qwen3"}'


@pytest.mark.anyio
async def test_run_until_client_disconnects_does_not_mistake_a_watcher_failure_for_a_disconnect():
    """A broken watcher must surface, not silently abort a client that is still there."""

    class BrokenRequest:
        async def is_disconnected(self):
            raise RuntimeError("receive channel is wrapped by something unexpected")

    async def work():
        await asyncio.sleep(5)

    with pytest.raises(RuntimeError, match="receive channel"):
        await run_until_client_disconnects(work(), BrokenRequest())


@pytest.mark.anyio
async def test_generic_proxy_handles_a_disconnect_while_reading_the_body(monkeypatch):
    """Leaving mid-upload raises starlette's ClientDisconnect, which must not become a 500."""

    class StubProxyService:
        async def proxy_generic_request(self, path, request):
            raise AssertionError("must not be reached: the body never arrived")

    monkeypatch.setattr(api, "get_proxy_service", lambda: StubProxyService())

    channel = FakeChannel([{"type": "http.disconnect"}])
    request = make_request("/api/generate", channel)

    response = await api.proxy_to_ollama(request, "api/generate")
    assert response.status_code == api.CLIENT_CLOSED_REQUEST


@pytest.mark.anyio
async def test_streaming_chat_is_left_to_starlette(monkeypatch):
    """The watcher must not touch the receive channel that starlette owns while streaming."""

    class StubProxyService:
        async def proxy_chat_with_tools(self, payload, stream=False):
            assert stream is True
            return StreamingResponse(iter(()))

    monkeypatch.setattr(api, "get_proxy_service", lambda: StubProxyService())

    channel = FakeChannel()
    request = make_request("/api/chat", channel)

    tasks_before = asyncio.all_tasks()
    response = await api.chat(request, {"stream": True, "messages": []})

    assert isinstance(response, StreamingResponse)
    assert channel.polls == 0
    assert asyncio.all_tasks() - tasks_before == set()
