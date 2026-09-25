---
title: "Running the tests"
description: "Run the Ollama MCP Bridge test suite with pytest: the unit tests CI runs, and the integration suite against a live bridge and Ollama server."
---

# Testing

```bash
uv run pytest                                        # everything
uv run pytest tests/ --ignore=tests/test_api.py -v   # what CI runs
uv run pytest tests/test_unit.py -v                  # one file
uv run pytest tests/test_unit.py::test_config_loading -v   # one test
```

## Unit tests

No running server required, which is why CI runs these.

```bash
uv run pytest tests/test_unit.py -v
```

They cover configuration loading, module imports and initialisation, project structure,
and tool definition formats.

## Integration tests

`tests/test_api.py` hits `http://localhost:8000` with `requests`, so it needs a live
bridge **and** a live Ollama. CI excludes it.

Run the server in one terminal:

```bash
ollama-mcp-bridge
```

and the tests in another:

```bash
uv run pytest tests/test_api.py -v
```

They cover the API endpoints over real HTTP, end-to-end behaviour against Ollama, and
tool calling with response integration.

## Manual checks

```bash
curl http://localhost:8000/health

curl http://localhost:8000/version

curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3:0.6b", "messages": [{"role": "user", "content": "What tools are available?"}]}'
```

That last one is a quick way to confirm your MCP servers connected and their tools made
it into the list.
