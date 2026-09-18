# Quick start

Three things have to be in place: Ollama running, a config file with at least one MCP
server, and the bridge itself.

## 1. Start Ollama

```bash
ollama serve
```

The bridge checks Ollama's health *before* binding its own port, so if this step is
missing you get a clear error instead of a server that half-starts.

## 2. Write an `mcp-config.json`

The repository ships a working example that launches a small mock weather server, so you
can exercise the bridge without any external MCP server:

```json title="mcp-config.json"
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": ["--directory", "./mock-weather-mcp-server", "run", "main.py"],
      "env": {
        "MCP_LOG_LEVEL": "ERROR"
      }
    }
  }
}
```

!!! info "Paths are relative to the config file"

    Not to the directory you run the bridge from. `./mock-weather-mcp-server` resolves
    next to `mcp-config.json`, which means you can move the config around without
    rewriting every path. The same rule drives
    [`${workspaceFolder}`](../configuration/variable-expansion.md).

## 3. Start the bridge

```bash
ollama-mcp-bridge
```

Defaults: config `./mcp-config.json`, host `0.0.0.0`, port `8000`, Ollama at
`http://localhost:11434`. On startup it connects every configured MCP server, collects
their tools and logs what it found.

## 4. Send a request

Point any Ollama client at the bridge instead of Ollama.

=== "Python"

    ```python
    from ollama import Client

    client = Client(host="http://localhost:8000")

    response = client.chat(
        model="qwen3:0.6b",
        messages=[{"role": "user", "content": "What is the weather like in Paris today?"}],
    )
    print(response["message"]["content"])
    ```

=== "curl"

    ```bash
    curl -N -X POST http://localhost:8000/api/chat \
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

The model will ask for the weather tool, the bridge will execute it against the MCP
server, feed the result back, and return the finished answer — all inside that one
request.

## What to read next

<div class="grid cards" markdown>

-   __Understand the loop__

    ---

    What the bridge does between receiving your request and answering it.

    [:octicons-arrow-right-24: How it works](../guide/how-it-works.md)

-   __Connect real servers__

    ---

    stdio, StreamableHTTP and SSE, plus per-server tool filtering.

    [:octicons-arrow-right-24: MCP servers](../configuration/mcp-servers.md)

</div>
