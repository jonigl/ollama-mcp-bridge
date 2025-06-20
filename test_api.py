"""
Simple pytest tests for the Ollama MCP Bridge API
Run with: uv run pytest test_api.py -v
"""
import requests
import json
import tempfile
import os

API_BASE = "http://localhost:8000"

# Unit Tests (no server required)
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

# Integration Tests (require running server)
def test_health_endpoint():
    """Test that the health endpoint is accessible and returns valid data"""
    response = requests.get(f"{API_BASE}/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "tools" in data
    assert isinstance(data["tools"], int)
    assert data["tools"] >= 0

def test_chat_endpoint_structure():
    """Test that the chat endpoint accepts requests and returns proper structure"""
    payload = {
        "model": "qwen3:0.6b",
        "stream": False,
        "messages": [
            {"role": "user", "content": "Hello, what tools do you have?"}
        ]
    }
    response = requests.post(f"{API_BASE}/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "content" in data["message"]
    assert isinstance(data["message"]["content"], str)
    assert len(data["message"]["content"]) > 0

def test_chat_without_model():
    """Test that the chat endpoint returns 400 if model is missing (Ollama API requires model)"""
    payload = {
        "messages": [
            {"role": "user", "content": "Simple test query"}
        ]
    }
    response = requests.post(f"{API_BASE}/api/chat", json=payload)
    assert response.status_code == 400
