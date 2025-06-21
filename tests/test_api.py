"""
Simple pytest tests for the Ollama MCP Bridge API
Run with: uv run pytest tests/test_api.py -v
"""
import requests

API_BASE = "http://localhost:8000"

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

def test_tags_endpoint():
    """Test that the tags endpoint proxies correctly and returns a models list"""
    response = requests.get(f"{API_BASE}/api/tags", timeout=10)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "models" in data
    assert isinstance(data["models"], list)
    # Optionally check that each model is a dict
    for model in data["models"]:
        assert isinstance(model, dict)
