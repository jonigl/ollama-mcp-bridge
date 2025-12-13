import types

import pytest


def test_get_ollama_proxy_timeout_config_unset(monkeypatch):
    monkeypatch.delenv("OLLAMA_PROXY_TIMEOUT", raising=False)

    from ollama_mcp_bridge.utils import get_ollama_proxy_timeout_config

    is_set, timeout_seconds = get_ollama_proxy_timeout_config()
    assert is_set is False
    assert timeout_seconds is None


def test_get_ollama_proxy_timeout_config_ms(monkeypatch):
    monkeypatch.setenv("OLLAMA_PROXY_TIMEOUT", "1500")

    from ollama_mcp_bridge.utils import get_ollama_proxy_timeout_config

    is_set, timeout_seconds = get_ollama_proxy_timeout_config()
    assert is_set is True
    assert timeout_seconds == 1.5


def test_get_ollama_proxy_timeout_config_zero_disables(monkeypatch):
    monkeypatch.setenv("OLLAMA_PROXY_TIMEOUT", "0")

    import ollama_mcp_bridge.utils as utils

    # Reset warn-once sentinel so this test is isolated.
    monkeypatch.setattr(utils, "_ollama_proxy_timeout_disabled_warned", False)

    is_set, timeout_seconds = utils.get_ollama_proxy_timeout_config()
    assert is_set is True
    assert timeout_seconds is None


def test_check_ollama_health_respects_env_override(monkeypatch):
    import ollama_mcp_bridge.utils as utils

    class DummyResp:
        status_code = 200

    called = {}

    def fake_get(url, timeout):
        called["timeout"] = timeout
        return DummyResp()

    monkeypatch.setattr(utils.httpx, "get", fake_get)

    # Env unset -> uses function arg
    monkeypatch.delenv("OLLAMA_PROXY_TIMEOUT", raising=False)
    assert utils.check_ollama_health("http://localhost:11434", timeout=7) is True
    assert called["timeout"] == 7

    # Env set -> overrides function arg
    monkeypatch.setenv("OLLAMA_PROXY_TIMEOUT", "1234")
    assert utils.check_ollama_health("http://localhost:11434", timeout=7) is True
    assert called["timeout"] == 1.234

    # Env 0 -> explicitly disables
    monkeypatch.setenv("OLLAMA_PROXY_TIMEOUT", "0")
    monkeypatch.setattr(utils, "_ollama_proxy_timeout_disabled_warned", False)
    assert utils.check_ollama_health("http://localhost:11434", timeout=7) is True
    assert called["timeout"] is None


def test_mcp_manager_http_client_timeout_from_env(monkeypatch):
    import ollama_mcp_bridge.mcp_manager as mcp_manager_mod

    constructed = []

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            constructed.append(kwargs.get("timeout", "__unset__"))

        async def aclose(self):
            return None

    monkeypatch.setattr(mcp_manager_mod.httpx, "AsyncClient", DummyAsyncClient)

    # Unset -> don't pass timeout
    monkeypatch.delenv("OLLAMA_PROXY_TIMEOUT", raising=False)
    constructed.clear()
    _ = mcp_manager_mod.MCPManager()
    assert constructed[-1] == "__unset__"

    # Set -> pass seconds
    monkeypatch.setenv("OLLAMA_PROXY_TIMEOUT", "1000")
    constructed.clear()
    _ = mcp_manager_mod.MCPManager()
    assert constructed[-1] == 1.0

    # 0 -> pass None (disable)
    monkeypatch.setenv("OLLAMA_PROXY_TIMEOUT", "0")
    constructed.clear()
    _ = mcp_manager_mod.MCPManager()
    assert constructed[-1] is None


def test_proxy_service_http_client_timeout_from_env(monkeypatch):
    import ollama_mcp_bridge.proxy_service as proxy_service_mod

    constructed = []

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            constructed.append(kwargs.get("timeout", "__unset__"))

        async def aclose(self):
            return None

    monkeypatch.setattr(proxy_service_mod.httpx, "AsyncClient", DummyAsyncClient)

    class DummyMCPManager:
        ollama_url = "http://localhost:11434"
        all_tools = []
        system_prompt = None

    # Unset -> preserve existing behavior for /api/chat (timeout=None)
    monkeypatch.delenv("OLLAMA_PROXY_TIMEOUT", raising=False)
    constructed.clear()
    _ = proxy_service_mod.ProxyService(DummyMCPManager())
    assert constructed[-1] is None

    # Set -> pass seconds
    monkeypatch.setenv("OLLAMA_PROXY_TIMEOUT", "5000")
    constructed.clear()
    _ = proxy_service_mod.ProxyService(DummyMCPManager())
    assert constructed[-1] == 5.0

    # 0 -> pass None (disable)
    monkeypatch.setenv("OLLAMA_PROXY_TIMEOUT", "0")
    constructed.clear()
    _ = proxy_service_mod.ProxyService(DummyMCPManager())
    assert constructed[-1] is None


@pytest.mark.anyio
async def test_check_ollama_health_async_respects_env_override(monkeypatch):
    import ollama_mcp_bridge.utils as utils

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.seen_timeout = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, timeout):
            self.seen_timeout = timeout
            return types.SimpleNamespace(status_code=200)

    dummy_client = DummyAsyncClient()

    def fake_async_client(*args, **kwargs):
        # Return the same instance so we can inspect it after the call.
        return dummy_client

    monkeypatch.setattr(utils.httpx, "AsyncClient", fake_async_client)

    # Env unset -> uses function arg
    monkeypatch.delenv("OLLAMA_PROXY_TIMEOUT", raising=False)
    assert (
        await utils.check_ollama_health_async("http://localhost:11434", timeout=9)
        is True
    )
    assert dummy_client.seen_timeout == 9

    # Env set -> overrides
    monkeypatch.setenv("OLLAMA_PROXY_TIMEOUT", "2000")
    assert (
        await utils.check_ollama_health_async("http://localhost:11434", timeout=9)
        is True
    )
    assert dummy_client.seen_timeout == 2.0

    # Env 0 -> disables
    monkeypatch.setenv("OLLAMA_PROXY_TIMEOUT", "0")
    monkeypatch.setattr(utils, "_ollama_proxy_timeout_disabled_warned", False)
    assert (
        await utils.check_ollama_health_async("http://localhost:11434", timeout=9)
        is True
    )
    assert dummy_client.seen_timeout is None


@pytest.mark.anyio
async def test_proxy_generic_request_sets_timeout_only_when_env_set(monkeypatch):
    import ollama_mcp_bridge.proxy_service as proxy_service_mod

    class DummyResponse:
        def __init__(self):
            self.content = b"{}"
            self.status_code = 200
            self.headers = {}

    constructed_timeouts = []

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            constructed_timeouts.append(kwargs.get("timeout", "__unset__"))

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, headers=None, params=None, content=None):
            return DummyResponse()

        async def aclose(self):
            return None

    monkeypatch.setattr(proxy_service_mod.httpx, "AsyncClient", DummyAsyncClient)

    class DummyMCPManager:
        ollama_url = "http://localhost:11434"
        all_tools = []
        system_prompt = None

        async def call_tool(self, tool_name, arguments):
            raise AssertionError("call_tool should not be used in this test")

    svc = proxy_service_mod.ProxyService(DummyMCPManager())

    class DummyRequest:
        method = "POST"

        def __init__(self):
            self.headers = {"content-type": "application/json", "host": "example"}
            self.query_params = {}

        async def body(self):
            return b"{}"

    req = DummyRequest()

    # Env unset -> do not pass timeout (httpx defaults)
    monkeypatch.delenv("OLLAMA_PROXY_TIMEOUT", raising=False)
    constructed_timeouts.clear()
    await svc.proxy_generic_request("api/tags", req)
    assert constructed_timeouts[-1] == "__unset__"

    # Env set -> pass timeout seconds
    monkeypatch.setenv("OLLAMA_PROXY_TIMEOUT", "2500")
    constructed_timeouts.clear()
    await svc.proxy_generic_request("api/tags", req)
    assert constructed_timeouts[-1] == 2.5

    # Env 0 -> pass timeout=None (disable)
    monkeypatch.setenv("OLLAMA_PROXY_TIMEOUT", "0")
    constructed_timeouts.clear()
    await svc.proxy_generic_request("api/tags", req)
    assert constructed_timeouts[-1] is None
