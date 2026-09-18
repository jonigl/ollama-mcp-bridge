# Environment variables

All of these can be set in the environment; most have a CLI equivalent, and
[the CLI flag always wins](cli.md).

| Variable | Default | CLI equivalent |
| --- | --- | --- |
| `OLLAMA_URL` | `http://localhost:11434` | [`--ollama-url`](cli.md#-ollama-url) |
| `UPSTREAM_HEADERS` | none | [`--upstream-header`](cli.md#-upstream-header) |
| `MAX_TOOL_ROUNDS` | unlimited | [`--max-tool-rounds`](cli.md#-max-tool-rounds) |
| `SYSTEM_PROMPT` | none | [`--system-prompt`](cli.md#-system-prompt) |
| `CORS_ORIGINS` | `*` | — |
| `OLLAMA_PROXY_TIMEOUT` | unset | — |

## `OLLAMA_URL`

The Ollama server to proxy to. Useful for Docker deployments where the URL comes from
the environment rather than the command line.

```bash
OLLAMA_URL=http://192.168.1.100:11434 ollama-mcp-bridge
```

## `UPSTREAM_HEADERS`

A JSON object of headers to send upstream. Individual headers can be added or overridden
with the repeatable `--upstream-header` flag.

```bash
UPSTREAM_HEADERS='{"Authorization": "Bearer token123", "X-API-Key": "secret"}' \
  ollama-mcp-bridge
```

Preferable to the CLI flag in Docker and systemd setups, where arguments show up in the
process list.

## `MAX_TOOL_ROUNDS`

```bash
MAX_TOOL_ROUNDS=5 ollama-mcp-bridge
```

## `SYSTEM_PROMPT`

```bash
SYSTEM_PROMPT="You are a concise assistant." ollama-mcp-bridge
```

## `CORS_ORIGINS`

Comma-separated list of allowed origins. See [CORS](cors.md).

## `OLLAMA_PROXY_TIMEOUT`

Timeout for HTTP requests the bridge sends to Ollama, **in milliseconds**.

It has three distinct states, and the difference matters:

**Unset** (the default)
:   Existing behaviour is preserved — some requests use library defaults, and `/api/chat`
    is not timed out at all. This is *not* the same as setting it to `0`.

**Greater than `0`**
:   Applied to Ollama-bound HTTP requests.

**Exactly `0`**
:   Timeouts are explicitly disabled. The bridge logs a warning.

```bash
# 10 minutes
OLLAMA_PROXY_TIMEOUT=600000 ollama-mcp-bridge
```

!!! note "Streaming ignores it"

    Streaming chat responses always run with no timeout, whatever this is set to.
