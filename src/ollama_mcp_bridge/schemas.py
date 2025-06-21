"""Schemas and examples for API endpoints."""

# Example for chat endpoint
CHAT_EXAMPLE = {
    "model": "qwen3:0.6b",
    "messages": [
        {"role": "system", "content": "You are a weather assistant."},
        {"role": "user", "content": "What's the weather like in Paris today?"}
    ],
    "think": True,
    "stream": False,
    "format": None,
    "options": {"temperature": 0.7, "top_p": 0.9}
}
