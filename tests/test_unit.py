"""
Unit tests that can run in GitHub Actions (no external services required)
Run with: uv run pytest tests/test_unit.py -v
"""

import json
import os
import subprocess
import tempfile
import sys
from pathlib import Path
import pytest

# Add src directory to path for testing when package is not installed
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_config_loading():
    """Test that configuration files are loaded correctly"""
    config_data = {
        "mcpServers": {
            "test_server": {
                "command": "test_command",
                "args": ["arg1", "arg2"],
                "env": {"TEST_VAR": "value"},
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            loaded_config = json.load(f)

        assert "mcpServers" in loaded_config
        assert "test_server" in loaded_config["mcpServers"]
        assert loaded_config["mcpServers"]["test_server"]["command"] == "test_command"
        assert loaded_config["mcpServers"]["test_server"]["args"] == ["arg1", "arg2"]
    finally:
        os.unlink(config_path)


def test_mcp_manager_initialization():
    """Test MCPManager can be initialized"""
    try:
        # Try importing from package if installed
        from ollama_mcp_bridge.mcp_manager import MCPManager
    except ImportError:
        # If package not installed, try importing from src
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from ollama_mcp_bridge.mcp_manager import MCPManager

    # Test initialization
    manager = MCPManager()

    # Test initial state
    assert len(manager.sessions) == 0
    assert len(manager.all_tools) == 0
    assert hasattr(manager, "http_client")
    assert hasattr(manager, "ollama_url")


def test_tool_definition_structure():
    """Test that tool definitions have the expected structure"""
    # Simulate a tool definition that would be created
    tool_def = {
        "type": "function",
        "function": {
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }

    assert tool_def["type"] == "function"
    assert "function" in tool_def
    assert "name" in tool_def["function"]
    assert "description" in tool_def["function"]
    assert "parameters" in tool_def["function"]


def test_project_structure():
    """Test that required project files exist"""
    root_path = Path(__file__).parent.parent
    src_root = root_path / "src" / "ollama_mcp_bridge"

    required_files = [
        "main.py",
        "api.py",
        "mcp_manager.py",
        "utils.py",
        "proxy_service.py",
    ]

    for file_name in required_files:
        file_path = src_root / file_name
        assert file_path.exists(), f"Required file {file_name} not found"


def test_imports():
    """Test that all modules can be imported without errors"""
    try:
        # Ensure src is in path
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

        # Import modules, using them to avoid unused import warnings
        from ollama_mcp_bridge import api, mcp_manager, utils, proxy_service

        assert api
        assert mcp_manager
        assert utils
        assert proxy_service
    except ImportError as e:
        assert False, f"Import failed: {e}"


def test_example_config_structure():
    """Test that the example config file has the correct structure"""
    config_path = Path(__file__).parent.parent / "mcp-config.json"

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        assert "mcpServers" in config
        assert isinstance(config["mcpServers"], dict)

        # Check each server has required fields
        for _, server_config in config["mcpServers"].items():
            # Servers can be configured either as:
            # - local process: {"command": "...", "args": [...], "env": {...}}
            # - remote endpoint: {"url": "https://..."}
            if "url" in server_config:
                assert isinstance(server_config["url"], str)
                assert server_config["url"], "Server url must be non-empty"
            else:
                assert "command" in server_config
                assert "args" in server_config
                assert isinstance(server_config["args"], list)


def test_validate_cli_max_tool_rounds():
    """Test that validate_cli_inputs enforces max_tool_rounds validation."""
    try:
        from ollama_mcp_bridge.utils import validate_cli_inputs
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from ollama_mcp_bridge.utils import validate_cli_inputs

    # Valid case: None
    validate_cli_inputs("mcp-config.json", "0.0.0.0", 8000, "http://localhost:11434", None, None)

    # Invalid max_tool_rounds (zero)
    from typer import BadParameter

    try:
        validate_cli_inputs("mcp-config.json", "0.0.0.0", 8000, "http://localhost:11434", 0, None)
        assert False, "Expected BadParameter for max_tool_rounds=0"
    except BadParameter:
        pass

    # Invalid max_tool_rounds (negative)
    try:
        validate_cli_inputs("mcp-config.json", "0.0.0.0", 8000, "http://localhost:11434", -1, None)
        assert False, "Expected BadParameter for max_tool_rounds=-1"
    except BadParameter:
        pass


def test_script_installed():
    try:
        result = subprocess.run(["ollama-mcp-bridge", "--help"], check=False)
        assert result.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError) as e:
        assert False, f"Subprocess call failed. Is the script installed? {e}"


@pytest.mark.anyio
async def test_system_prompt_prepended():
    """Test that the system prompt configured on MCPManager is prepended to messages."""
    try:
        from ollama_mcp_bridge.mcp_manager import MCPManager
        from ollama_mcp_bridge.proxy_service import ProxyService
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from ollama_mcp_bridge.mcp_manager import MCPManager
        from ollama_mcp_bridge.proxy_service import ProxyService

    mgr = MCPManager(system_prompt="You are a helpful assistant.")
    ps = ProxyService(mgr)
    try:
        # Case: user message only -> system prompt should be prepended
        messages = [{"role": "user", "content": "Hello"}]
        out = ps._maybe_prepend_system_prompt(messages)
        assert out[0]["role"] == "system"
        assert out[0]["content"] == "You are a helpful assistant."

        # Case: existing system prompt should not be duplicated or replaced
        messages2 = [
            {"role": "system", "content": "Existing"},
            {"role": "user", "content": "Hi"},
        ]
        out2 = ps._maybe_prepend_system_prompt(messages2)
        assert out2[0]["role"] == "system"
        assert out2[0]["content"] == "Existing"

        # Case: empty messages -> system prompt becomes the only message
        out3 = ps._maybe_prepend_system_prompt([])
        assert out3[0]["role"] == "system"
        assert out3[0]["content"] == "You are a helpful assistant."
    finally:
        await ps.cleanup()
        await mgr.http_client.aclose()


@pytest.mark.anyio
async def test_proxy_service_applies_configured_ollama_headers():
    """Test that configured Ollama headers are attached to upstream chat requests."""
    try:
        from ollama_mcp_bridge.mcp_manager import MCPManager
        from ollama_mcp_bridge.proxy_service import ProxyService
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from ollama_mcp_bridge.mcp_manager import MCPManager
        from ollama_mcp_bridge.proxy_service import ProxyService

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "ok"}}

    class DummyClient:
        def __init__(self):
            self.calls = []

        async def post(self, url, json=None, headers=None):
            self.calls.append({"url": url, "json": json, "headers": headers})
            return DummyResponse()

        async def aclose(self):
            return None

    mgr = MCPManager(ollama_headers={"X-API-Key": "secret"})
    ps = ProxyService(mgr)
    original_http_client = ps.http_client
    ps.http_client = DummyClient()
    try:
        result = await ps._proxy_with_tools_non_streaming(
            "/api/chat",
            {"model": "test-model", "messages": [{"role": "user", "content": "Hello"}]},
        )

        assert result["message"]["content"] == "ok"
        assert ps.http_client.calls[0]["headers"] == {"X-API-Key": "secret"}
    finally:
        dummy_client = ps.http_client
        ps.http_client = original_http_client
        await dummy_client.aclose()
        await original_http_client.aclose()
        await mgr.http_client.aclose()


@pytest.mark.anyio
async def test_proxy_service_merges_request_headers_with_configured_ollama_headers():
    """Test that configured Ollama headers override conflicting forwarded request headers."""
    try:
        from ollama_mcp_bridge.mcp_manager import MCPManager
        from ollama_mcp_bridge.proxy_service import ProxyService
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from ollama_mcp_bridge.mcp_manager import MCPManager
        from ollama_mcp_bridge.proxy_service import ProxyService

    mgr = MCPManager(ollama_headers={"X-API-Key": "secret"})
    ps = ProxyService(mgr)
    try:
        headers = ps._get_ollama_headers({"Accept": "application/json", "X-API-Key": "client-value"})

        assert headers == {"Accept": "application/json", "X-API-Key": "secret"}

        # Forwarded headers arrive lowercased (per the ASGI spec), so the override
        # must be case-insensitive or both values would be sent upstream.
        headers_case_mismatch = ps._get_ollama_headers({"accept": "application/json", "x-api-key": "client-value"})

        assert headers_case_mismatch == {"accept": "application/json", "X-API-Key": "secret"}
    finally:
        await ps.cleanup()
        await mgr.http_client.aclose()


@pytest.mark.anyio
async def test_streaming_tool_round_is_not_exposed_to_client(monkeypatch):
    """A tool-call round must not reach the client as tool calls nor as a completion event."""
    from ollama_mcp_bridge import proxy_service
    from ollama_mcp_bridge.mcp_manager import MCPManager

    responses = iter(
        [
            [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{"function": {"name": "test_tool", "arguments": {}}}],
                    },
                    "done": False,
                },
                {"message": {"role": "assistant", "content": ""}, "done": True},
            ],
            [
                {"message": {"role": "assistant", "content": "Final answer"}, "done": False},
                {"message": {"role": "assistant", "content": ""}, "done": True},
            ],
        ]
    )

    async def fake_iter_ndjson_chunks(_):
        for response in next(responses):
            yield response

    async def fake_call_tool(_, __):
        return "tool result"

    monkeypatch.setattr(proxy_service, "iter_ndjson_chunks", fake_iter_ndjson_chunks)
    manager = MCPManager()
    manager.all_tools = [{"type": "function", "function": {"name": "test_tool"}}]
    manager.call_tool = fake_call_tool
    service = proxy_service.ProxyService(manager)
    try:
        chunks = [
            json.loads(chunk) async for chunk in service._proxy_with_tools_streaming("/api/chat", {"messages": []})
        ]
        # No tool call may reach the client, and the tool round must not look finished
        assert all("tool_calls" not in chunk["message"] for chunk in chunks)
        assert sum(1 for chunk in chunks if chunk.get("done")) == 1
        assert chunks[-1]["done"] is True
        assert "".join(chunk["message"].get("content", "") for chunk in chunks) == "Final answer"
    finally:
        await service.cleanup()
        await manager.http_client.aclose()


@pytest.mark.anyio
async def test_streaming_keeps_content_and_thinking_of_a_tool_round(monkeypatch):
    """Only the tool calls are stripped: content and thinking from that round still stream."""
    from ollama_mcp_bridge import proxy_service
    from ollama_mcp_bridge.mcp_manager import MCPManager

    responses = iter(
        [
            [
                {"message": {"role": "assistant", "content": "", "thinking": "I need the tool"}, "done": False},
                {
                    "message": {
                        "role": "assistant",
                        "content": "Let me check. ",
                        "tool_calls": [{"function": {"name": "test_tool", "arguments": {}}}],
                    },
                    "done": False,
                },
                {"message": {"role": "assistant", "content": ""}, "done": True},
            ],
            [
                {"message": {"role": "assistant", "content": "Final answer"}, "done": False},
                {"message": {"role": "assistant", "content": ""}, "done": True},
            ],
        ]
    )

    async def fake_iter_ndjson_chunks(_):
        for response in next(responses):
            yield response

    captured = {}

    async def fake_call_tool(_, __):
        return "tool result"

    monkeypatch.setattr(proxy_service, "iter_ndjson_chunks", fake_iter_ndjson_chunks)
    manager = MCPManager()
    manager.all_tools = [{"type": "function", "function": {"name": "test_tool"}}]
    manager.call_tool = fake_call_tool
    service = proxy_service.ProxyService(manager)

    original_handle = service._handle_tool_calls

    async def spy(messages, tool_calls):
        captured["assistant"] = messages[-1]
        return await original_handle(messages, tool_calls)

    service._handle_tool_calls = spy

    try:
        chunks = [
            json.loads(chunk) async for chunk in service._proxy_with_tools_streaming("/api/chat", {"messages": []})
        ]

        assert chunks == [
            {"message": {"role": "assistant", "content": "", "thinking": "I need the tool"}, "done": False},
            {"message": {"role": "assistant", "content": "Let me check. "}, "done": False},
            {"message": {"role": "assistant", "content": "Final answer"}, "done": False},
            {"message": {"role": "assistant", "content": ""}, "done": True},
        ]
        # No chunk may leak tool calls to the client.
        assert all("tool_calls" not in chunk["message"] for chunk in chunks)
        # The content streamed in the tool round is kept in the history sent to Ollama
        assert captured["assistant"]["content"] == "Let me check. "
    finally:
        await service.cleanup()
        await manager.http_client.aclose()


@pytest.mark.anyio
async def test_streaming_collects_parallel_tool_calls_streamed_in_separate_chunks(monkeypatch):
    """Ollama streams one complete tool call per chunk, so every one of them must run."""
    from ollama_mcp_bridge import proxy_service
    from ollama_mcp_bridge.mcp_manager import MCPManager

    def call_chunk(index, city):
        return {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": f"call_{index}",
                        "function": {"index": index, "name": "test_tool", "arguments": {"city": city}},
                    }
                ],
            },
            "done": False,
        }

    responses = iter(
        [
            [
                call_chunk(0, "Barcelona"),
                call_chunk(1, "Madrid"),
                call_chunk(2, "Tokyo"),
                {"message": {"role": "assistant", "content": ""}, "done": True},
            ],
            [
                {"message": {"role": "assistant", "content": "All three"}, "done": False},
                {"message": {"role": "assistant", "content": ""}, "done": True},
            ],
        ]
    )

    async def fake_iter_ndjson_chunks(_):
        for response in next(responses):
            yield response

    executed = []

    async def fake_call_tool(name, arguments):
        executed.append(arguments["city"])
        return "20C"

    monkeypatch.setattr(proxy_service, "iter_ndjson_chunks", fake_iter_ndjson_chunks)
    manager = MCPManager()
    manager.all_tools = [{"type": "function", "function": {"name": "test_tool"}}]
    manager.call_tool = fake_call_tool
    service = proxy_service.ProxyService(manager)
    try:
        chunks = [
            json.loads(chunk) async for chunk in service._proxy_with_tools_streaming("/api/chat", {"messages": []})
        ]

        # All three parallel calls run: a later chunk must not replace the earlier ones.
        assert executed == ["Barcelona", "Madrid", "Tokyo"]
        assert sum(1 for chunk in chunks if chunk.get("done")) == 1
    finally:
        await service.cleanup()
        await manager.http_client.aclose()


def test_is_port_in_use():
    """Test the is_port_in_use utility."""
    import socket
    from ollama_mcp_bridge.utils import is_port_in_use

    # Find an open port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        _, port = s.getsockname()

    # The port should be free now that the socket is closed
    has_error, error_msg = is_port_in_use("127.0.0.1", port)
    assert not has_error
    assert error_msg is None

    # Now bind it and check
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))
        has_error, error_msg = is_port_in_use("127.0.0.1", port)
        assert has_error
        assert "already in use" in error_msg

    # Test invalid host
    has_error, error_msg = is_port_in_use("invalid.host.name.test", 8000)
    assert has_error
    assert error_msg is not None


def test_cli_exit_if_port_in_use(monkeypatch):
    """Test that the CLI app exits if the port is already in use."""
    from ollama_mcp_bridge.main import cli_app
    import typer
    from unittest.mock import MagicMock

    # Mock dependencies to avoid actually running the app
    monkeypatch.setattr("ollama_mcp_bridge.main.is_port_in_use", lambda h, p: (True, "Port already in use"))
    monkeypatch.setattr("ollama_mcp_bridge.main.validate_cli_inputs", MagicMock())

    try:
        cli_app(port=8000, version=False, upstream_header=[])
        assert False, "Should have raised typer.Exit(1)"
    except typer.Exit as e:
        assert e.exit_code == 1
