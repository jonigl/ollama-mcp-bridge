# Search the web from Ollama

This opt-in configuration connects Ollama MCP Bridge to the
[Parallel Search MCP](https://docs.parallel.ai/search/search-mcp) over
StreamableHTTP. It provides `parallel.web_search` for web searches and
`parallel.web_fetch` for reading specific URLs. The service is free for light use
without an API key, subject to anonymous rate limits. It requires internet access;
search queries and fetched URLs are sent to Parallel.

From the repository root, with Ollama running and a tool-capable model installed:

```bash
uv sync
uv run ollama-mcp-bridge --config examples/parallel-search/mcp-config.json
```

In another terminal, send a non-streaming chat request. Replace `YOUR_MODEL` with
an installed Ollama model that supports tool calling:

```bash
curl http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "YOUR_MODEL",
    "stream": false,
    "messages": [{
      "role": "user",
      "content": "Use parallel.web_search to find the official Python asyncio documentation, then use parallel.web_fetch to read it and explain what asyncio is with a source URL."
    }]
  }'
```

Startup logs should show both tools on the `parallel` server. The model decides
whether to call tools; the bridge forwards their results back to the model for
its final answer. If tools are missing, check the startup connection errors and
network access. Anonymous rate limits or remote service errors may prevent a
search even when startup succeeds.

The example sends `User-Agent: ollama-mcp-bridge` and includes only the two search
tools. It contains no credentials and does not load a dotenv file. No API key or
authentication header is needed for this endpoint.

Selecting this file loads only Parallel. To keep your other servers, copy its
`parallel` entry into your own `mcpServers` object instead. Keep any existing
relative paths in their original configuration directory. The repository's
root `mcp-config.json`, default weather server, and CLI defaults are unchanged.

## Test the example

The offline test uses an HTTP MCP protocol fixture and controlled Ollama responses
to exercise startup, discovery, tool filtering, search/fetch dispatch, and the
final `/api/chat` response without downloading a model:

```bash
uv run pytest tests/test_parallel_search_example.py -q
```

To test the same path against the live, anonymous Parallel endpoint:

```bash
PARALLEL_EXAMPLE_LIVE=1 uv run pytest tests/test_parallel_search_example.py -q
```

The live test sends a Python documentation search and fetch request to Parallel.
It still uses controlled Ollama responses, so it tests bridge integration rather
than a particular model's ability to choose tools. It makes no authenticated
requests and may fail when the service is unavailable or rate limited.
