---
title: "Ollama-compatible API reference"
description: "Ollama MCP Bridge endpoints: /api/chat with MCP tools, /health, /version, and every other Ollama API path proxied unchanged as a drop-in replacement."
---

# API reference

The bridge listens on `http://localhost:8000` by default and mirrors the Ollama API.
Interactive Swagger UI is at [`/docs`](http://localhost:8000/docs) while it's running.

## Endpoints

### `POST /api/chat`

Ollama's chat endpoint, **plus MCP tools**. This is the only endpoint where tools are
integrated; the tool-calling loop runs server-side and the client sees a single
request/response exchange.

Accepts the same payload as Ollama, including `stream`, `think` and `options`.

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3:0.6b",
    "messages": [
      {"role": "system", "content": "You are a weather assistant."},
      {"role": "user", "content": "What is the weather like in Paris today?"}
    ],
    "think": true,
    "stream": true,
    "options": {"temperature": 0.7, "top_p": 0.9}
  }'
```

### `GET /health`

Bridge health and status. Not proxied to Ollama.

```bash
curl http://localhost:8000/health
```

### `GET /version`

Installed version plus the result of the PyPI update check. Not proxied.

```bash
curl http://localhost:8000/version
```

### Everything else

Every other path and method is proxied to Ollama verbatim — `/api/generate`,
`/api/tags`, `/api/embed`, `/api/pull`, and anything Ollama adds later. The catch-all
route matches all methods, so no endpoint list needs maintaining.

!!! important "Only `/api/chat` gets tools"

    `/health` and `/version` belong to the bridge. Everything else is a transparent
    passthrough. If you need MCP tools, you need `/api/chat`.

## Using it as a drop-in

The bridge is a drop-in proxy for the Ollama API. Existing clients and libraries keep
working against both local and cloud Ollama models — change the host and nothing else.

```python
from ollama import Client

client = Client(host="http://localhost:8000")
client.chat(model="qwen3", messages=[...])
```

!!! tip

    `/docs` gives you the whole surface interactively, which is usually faster than
    reading this page.
