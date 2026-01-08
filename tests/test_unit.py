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


def test_system_prompt_prepended():
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
        cli_app(port=8000, version=False)
        assert False, "Should have raised typer.Exit(1)"
    except typer.Exit as e:
        assert e.exit_code == 1
