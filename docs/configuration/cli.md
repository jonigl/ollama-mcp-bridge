---
title: "CLI options reference"
description: "Every ollama-mcp-bridge command-line flag: config file, host, port, Ollama URL, upstream headers, max tool rounds, system prompt and more."
---

# CLI options

```bash
ollama-mcp-bridge [OPTIONS]
```

Every option that has an environment-variable equivalent follows the same rule:
**the CLI flag wins over the environment variable.**

## Options

### `--config`

Path to the MCP configuration file.

**Default:** `mcp-config.json`

```bash
ollama-mcp-bridge --config /path/to/custom-config.json
```

### `--host`

Host to bind the server to.

**Default:** `0.0.0.0`

### `--port`

Port to bind the server to. Checked for availability *before* uvicorn starts, so a
collision fails fast with a readable error.

**Default:** `8000`

```bash
ollama-mcp-bridge --host 0.0.0.0 --port 8080
```

### `--ollama-url`

The Ollama server to proxy to. Works with local, remote and cloud Ollama.

**Default:** `http://localhost:11434` · **Env:** `OLLAMA_URL`

```bash
ollama-mcp-bridge --ollama-url http://192.168.1.100:11434
```

### `--upstream-header`

A header to attach to every request the bridge sends upstream, in curl style
(`"Name: Value"`). Repeatable.

**Env:** `UPSTREAM_HEADERS` (a JSON object)

```bash
ollama-mcp-bridge --upstream-header "X-API-Key: your-key"

ollama-mcp-bridge \
  --upstream-header "Authorization: Bearer xxx" \
  --upstream-header "X-API-Key: yyy"
```

Let the shell expand a variable to keep secrets out of your shell history:

```bash
ollama-mcp-bridge --upstream-header "Authorization: Bearer $MY_API_KEY"
```

!!! info "These target the hop *before* Ollama"

    Ollama itself doesn't consume these headers. They're for whatever sits between the
    bridge and Ollama — a reverse proxy, gateway or auth layer.

    They're applied to health checks, `/api/chat`, and every transparently proxied
    endpoint. On the proxy path, a forwarded client header whose lowercased name
    collides with a configured one is dropped, so a header is never sent twice.

### `--max-tool-rounds`

Maximum number of tool-execution rounds per chat request.

**Default:** unlimited · **Env:** `MAX_TOOL_ROUNDS`

```bash
ollama-mcp-bridge --max-tool-rounds 5
```

When the limit is reached the bridge makes one final call to Ollama with no tools
attached, so the model has to produce an answer instead of asking for another tool.

### `--system-prompt`

A system prompt prepended to every `/api/chat` request.

**Default:** none · **Env:** `SYSTEM_PROMPT`

```bash
ollama-mcp-bridge --system-prompt "You are a concise assistant."
```

If the incoming `messages` array already starts with a system message, the request is
left alone.

### `--reload`

Enable auto-reload. For development only.

### `--version`

Print version information, check PyPI for a newer release, and exit.

## Combining options

```bash
ollama-mcp-bridge \
  --config custom.json \
  --host 0.0.0.0 \
  --port 8080 \
  --ollama-url http://remote-ollama:11434 \
  --max-tool-rounds 10
```

With an upstream API key:

```bash
ollama-mcp-bridge \
  --config custom.json \
  --ollama-url http://remote-ollama:11434 \
  --upstream-header "X-API-Key: your-key" \
  --port 8080
```
