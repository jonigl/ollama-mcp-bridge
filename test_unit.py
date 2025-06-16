"""
Unit tests that can run in GitHub Actions (no external services required)
Run with: uv run pytest test_unit.py -v
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path


def test_config_loading():
    """Test that configuration files are loaded correctly"""
    config_data = {
        "mcpServers": {
            "test_server": {
                "command": "test_command",
                "args": ["arg1", "arg2"],
                "env": {"TEST_VAR": "value"}
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            loaded_config = json.load(f)

        assert "mcpServers" in loaded_config
        assert "test_server" in loaded_config["mcpServers"]
        assert loaded_config["mcpServers"]["test_server"]["command"] == "test_command"
        assert loaded_config["mcpServers"]["test_server"]["args"] == ["arg1", "arg2"]
    finally:
        os.unlink(config_path)

def test_mcp_manager_initialization():
    """Test MCPManager can be initialized"""
    from mcp_manager import MCPManager

    # Test initialization
    manager = MCPManager()

    # Test initial state
    assert len(manager.sessions) == 0
    assert len(manager.all_tools) == 0
    assert manager.ollama_client is not None

def test_tool_definition_structure():
    """Test that tool definitions have the expected structure"""
    # Simulate a tool definition that would be created
    tool_def = {
        "type": "function",
        "function": {
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }

    assert tool_def["type"] == "function"
    assert "function" in tool_def
    assert "name" in tool_def["function"]
    assert "description" in tool_def["function"]
    assert "parameters" in tool_def["function"]

def test_project_structure():
    """Test that required project files exist"""
    project_root = Path(__file__).parent

    required_files = [
        "main.py",
        "api.py",
        "mcp_manager.py",
        "pyproject.toml",
        "mcp-config.json"
    ]

    for file_name in required_files:
        file_path = project_root / file_name
        assert file_path.exists(), f"Required file {file_name} not found"

def test_imports():
    """Test that all modules can be imported without errors"""
    try:
        import api
        import mcp_manager
        assert True  # If we get here, imports worked
    except ImportError as e:
        assert False, f"Import failed: {e}"

def test_example_config_structure():
    """Test that the example config file has the correct structure"""
    config_path = Path(__file__).parent / "mcp-config.json"

    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        assert "mcpServers" in config
        assert isinstance(config["mcpServers"], dict)

        # Check each server has required fields
        for server_name, server_config in config["mcpServers"].items():
            assert "command" in server_config
            assert "args" in server_config
            assert isinstance(server_config["args"], list)

def test_script_installed():
    try:
        result = subprocess.run(["ollama-mcp-bridge", "--help"])
        assert result.returncode == 0
    except Exception as e:
        assert False, f"Subprocess call failed. Is the script installed?, {e}"