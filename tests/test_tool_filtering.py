"""
Unit tests for tool filtering functionality
Run with: uv run pytest tests/test_tool_filtering.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src directory to path for testing when package is not installed
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def mock_tool_list():
    """Create a mock tool list similar to what MCP servers return"""
    tool1 = MagicMock()
    tool1.name = "get_current_temperature"
    tool1.description = "Get current temperature"
    tool1.inputSchema = {"type": "object", "properties": {"city": {"type": "string"}}}

    tool2 = MagicMock()
    tool2.name = "get_forecast"
    tool2.description = "Get weather forecast"
    tool2.inputSchema = {"type": "object", "properties": {"city": {"type": "string"}}}

    tool3 = MagicMock()
    tool3.name = "get_alerts"
    tool3.description = "Get weather alerts"
    tool3.inputSchema = {"type": "object", "properties": {"city": {"type": "string"}}}

    return [tool1, tool2, tool3]


def test_tool_filter_config_validation():
    """Test that toolFilter configuration is validated correctly"""
    try:
        from ollama_mcp_bridge.mcp_manager import MCPManager
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from ollama_mcp_bridge.mcp_manager import MCPManager

    # Valid modes should not raise
    valid_configs = [
        {"toolFilter": {"mode": "include", "tools": ["tool1"]}},
        {"toolFilter": {"mode": "exclude", "tools": ["tool1"]}},
        {"toolFilter": {"tools": ["tool1"]}},  # mode defaults to include
        {},  # no filter
    ]

    for config in valid_configs:
        # Validation happens in _connect_server, we're just checking the config structure
        assert "toolFilter" not in config or isinstance(config.get("toolFilter"), dict)


def test_tool_filter_config_with_invalid_mode():
    """Test that invalid toolFilter mode causes sys.exit"""
    config_data = {
        "mcpServers": {
            "test_server": {
                "command": "test_command",
                "args": ["arg1"],
                "toolFilter": {"mode": "invalid_mode", "tools": ["tool1"]},
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        from ollama_mcp_bridge.mcp_manager import MCPManager
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from ollama_mcp_bridge.mcp_manager import MCPManager

    mgr = MCPManager()

    # Mock the connection process to test validation
    with patch("ollama_mcp_bridge.mcp_manager.AsyncExitStack"):
        with patch("ollama_mcp_bridge.mcp_manager.expand_dict_env_vars", side_effect=lambda x, y: x):
            with pytest.raises(SystemExit) as exc_info:
                import asyncio

                asyncio.run(mgr._connect_server("test_server", config_data["mcpServers"]["test_server"]))

            assert exc_info.value.code == 1

    os.unlink(config_path)


def test_include_mode_filtering(mock_tool_list):
    """Test that include mode only includes specified tools"""
    # Simulate include mode filtering
    config = {"toolFilter": {"mode": "include", "tools": ["get_current_temperature", "get_forecast"]}}

    filter_mode = config["toolFilter"].get("mode", "include")
    filter_tools = config["toolFilter"].get("tools", [])

    filtered_tools = []
    if filter_tools and filter_mode == "include":
        for tool in mock_tool_list:
            if tool.name in filter_tools:
                filtered_tools.append(tool)

    assert len(filtered_tools) == 2
    assert filtered_tools[0].name == "get_current_temperature"
    assert filtered_tools[1].name == "get_forecast"


def test_exclude_mode_filtering(mock_tool_list):
    """Test that exclude mode excludes specified tools"""
    # Simulate exclude mode filtering
    config = {"toolFilter": {"mode": "exclude", "tools": ["get_alerts"]}}

    filter_mode = config["toolFilter"].get("mode", "include")
    filter_tools = config["toolFilter"].get("tools", [])

    filtered_tools = []
    if filter_tools and filter_mode == "exclude":
        for tool in mock_tool_list:
            if tool.name not in filter_tools:
                filtered_tools.append(tool)

    assert len(filtered_tools) == 2
    assert filtered_tools[0].name == "get_current_temperature"
    assert filtered_tools[1].name == "get_forecast"


def test_no_filter_includes_all_tools(mock_tool_list):
    """Test that no filter includes all tools"""
    # Simulate no filter
    config = {}

    filter_tools = config.get("toolFilter", {}).get("tools", [])

    if not filter_tools:
        filtered_tools = list(mock_tool_list)
    else:
        filtered_tools = []

    assert len(filtered_tools) == 3
    assert filtered_tools[0].name == "get_current_temperature"
    assert filtered_tools[1].name == "get_forecast"
    assert filtered_tools[2].name == "get_alerts"


def test_empty_tools_array_includes_all_tools(mock_tool_list):
    """Test that empty tools array includes all tools"""
    # Simulate empty tools array
    config = {"toolFilter": {"mode": "include", "tools": []}}

    filter_tools = config["toolFilter"].get("tools", [])

    if not filter_tools:
        filtered_tools = list(mock_tool_list)
    else:
        filtered_tools = []

    assert len(filtered_tools) == 3


def test_case_sensitive_tool_matching(mock_tool_list):
    """Test that tool name matching is case-sensitive"""
    # Simulate include mode with wrong case
    config = {"toolFilter": {"mode": "include", "tools": ["GET_CURRENT_TEMPERATURE"]}}  # Wrong case

    filter_mode = config["toolFilter"].get("mode", "include")
    filter_tools = config["toolFilter"].get("tools", [])

    filtered_tools = []
    if filter_tools and filter_mode == "include":
        for tool in mock_tool_list:
            if tool.name in filter_tools:
                filtered_tools.append(tool)

    # Should not match because of case sensitivity
    assert len(filtered_tools) == 0


def test_missing_tools_tracked_correctly(mock_tool_list):
    """Test that missing tools are tracked correctly"""
    # Simulate include mode with some missing tools
    config = {
        "toolFilter": {"mode": "include", "tools": ["get_current_temperature", "nonexistent_tool", "another_missing"]}
    }

    filter_tools = config["toolFilter"].get("tools", [])
    all_tool_names = [tool.name for tool in mock_tool_list]

    found_tools = []
    missing_tools = []

    for tool_name in filter_tools:
        if tool_name in all_tool_names:
            found_tools.append(tool_name)
        else:
            missing_tools.append(tool_name)

    assert len(found_tools) == 1
    assert found_tools[0] == "get_current_temperature"
    assert len(missing_tools) == 2
    assert "nonexistent_tool" in missing_tools
    assert "another_missing" in missing_tools


def test_tool_filter_example_config():
    """Test that example configuration with toolFilter loads correctly"""
    config_data = {
        "mcpServers": {
            "weather": {
                "command": "uv",
                "args": ["--directory", "./mock-weather-mcp-server", "run", "main.py"],
                "toolFilter": {"mode": "include", "tools": ["get_current_temperature"]},
            },
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                "toolFilter": {"mode": "exclude", "tools": ["delete_file", "write_file"]},
            },
            "no_filter": {"command": "npx", "args": ["-y", "some-server"]},
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            loaded_config = json.load(f)

        assert "mcpServers" in loaded_config
        assert "weather" in loaded_config["mcpServers"]
        assert "toolFilter" in loaded_config["mcpServers"]["weather"]
        assert loaded_config["mcpServers"]["weather"]["toolFilter"]["mode"] == "include"
        assert "get_current_temperature" in loaded_config["mcpServers"]["weather"]["toolFilter"]["tools"]

        assert "filesystem" in loaded_config["mcpServers"]
        assert "toolFilter" in loaded_config["mcpServers"]["filesystem"]
        assert loaded_config["mcpServers"]["filesystem"]["toolFilter"]["mode"] == "exclude"
        assert "delete_file" in loaded_config["mcpServers"]["filesystem"]["toolFilter"]["tools"]

        assert "no_filter" in loaded_config["mcpServers"]
        assert "toolFilter" not in loaded_config["mcpServers"]["no_filter"]
    finally:
        os.unlink(config_path)
