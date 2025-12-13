import pytest
import json
import tempfile
import os
from ollama_mcp_bridge.mcp_manager import MCPManager


@pytest.mark.anyio
async def test_invalid_json_config():
    manager = MCPManager()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{invalid_json")
        config_path = f.name

    try:
        with pytest.raises(ValueError, match="Invalid JSON"):
            await manager.load_servers(config_path)
    finally:
        os.unlink(config_path)


@pytest.mark.anyio
async def test_missing_mcp_servers_key():
    manager = MCPManager()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"other_key": {}}, f)
        config_path = f.name

    try:
        with pytest.raises(ValueError, match="missing 'mcpServers' key"):
            await manager.load_servers(config_path)
    finally:
        os.unlink(config_path)


@pytest.mark.anyio
async def test_connection_failure_handling():
    manager = MCPManager()
    # Config with one valid (mocked later if needed, but here we expect failure) and one invalid server
    # Since we don't want to actually run a server, we'll use a command that fails
    config_data = {"mcpServers": {"bad_server": {"command": "non_existent_command_xyz", "args": []}}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        # Should NOT raise exception, but log error
        await manager.load_servers(config_path)
        assert len(manager.sessions) == 0
        assert len(manager.all_tools) == 0
    finally:
        os.unlink(config_path)
        await manager.cleanup()
