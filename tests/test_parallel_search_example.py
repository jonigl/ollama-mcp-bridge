"""Exercise the optional configuration through startup and the public chat endpoint."""

import json
import os
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import httpx
from fastapi.testclient import TestClient

from ollama_mcp_bridge.api import app
from ollama_mcp_bridge import lifecycle

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/parallel-search/mcp-config.json"
SOURCE_URL = "https://docs.python.org/3/library/asyncio.html"
OBJECTIVE = "Find official Python documentation explaining asyncio."
SEARCH_ARGS = {"objective": OBJECTIVE, "search_queries": ["Python asyncio official documentation"]}
FETCH_ARGS = {"urls": [SOURCE_URL]}


@contextmanager
def http_fixture(handler):
    """Serve HTTP on an OS-assigned port, with deterministic cleanup."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class JsonHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_json(self, value):
        data = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        return json.loads(self.rfile.read(int(self.headers["Content-Length"])))


class MCPFixture(JsonHandler):
    """Minimal stateless StreamableHTTP server, used with the real MCP SDK client."""

    def do_GET(self):
        self.send_error(405)

    def do_POST(self):
        request = self.read_json()
        method = request["method"]
        if "id" not in request:
            self.send_response(202)
            self.end_headers()
            return
        if method == "initialize":
            result = {
                "protocolVersion": request["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "search-fixture", "version": "1"},
            }
        elif method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": name,
                        "description": name,
                        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": True},
                    }
                    for name in ("web_search", "web_fetch", "unrelated_tool")
                ]
            }
        elif method == "tools/call":
            params = request["params"]
            assert params["name"] in ("web_search", "web_fetch")
            expected = SEARCH_ARGS if params["name"] == "web_search" else FETCH_ARGS
            assert params["arguments"] == expected
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": f"{SOURCE_URL}\nasyncio is a library to write concurrent code using async/await syntax.",
                    }
                ],
                "isError": False,
            }
        else:
            raise AssertionError(f"Unexpected MCP method: {method}")
        self.send_json({"jsonrpc": "2.0", "id": request["id"], "result": result})


class OllamaFixture(JsonHandler):
    """Controlled model output; actual discovery and tool execution stay in the bridge."""

    def do_GET(self):
        self.send_json({"models": []})

    def do_POST(self):
        payload = self.read_json()
        assert payload["stream"] is False
        assert {t["function"]["name"] for t in payload["tools"]} == {
            "parallel.web_search",
            "parallel.web_fetch",
        }
        results = [m for m in payload["messages"] if m["role"] == "tool"]
        if len(results) < 2:
            name, args = ("web_search", SEARCH_ARGS) if not results else ("web_fetch", FETCH_ARGS)
            message = {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": f"parallel.{name}", "arguments": args}}],
            }
        else:
            assert [m["tool_name"] for m in results] == ["parallel.web_search", "parallel.web_fetch"]
            for result in results:
                assert "asyncio" in result["content"].lower()
                assert SOURCE_URL in result["content"]
                assert not result["content"].startswith("Error")
            # Return the actual fetch output, so the client receives useful source content.
            message = {"role": "assistant", "content": results[-1]["content"]}
        self.send_json({"message": message, "done": True})


def test_parallel_example_chat(tmp_path, monkeypatch):
    config = json.loads(EXAMPLE.read_text())
    assert config["mcpServers"]["parallel"]["url"] == "https://search.parallel.ai/mcp"
    assert config["mcpServers"]["parallel"]["headers"] == {"User-Agent": "ollama-mcp-bridge"}
    root_config = EXAMPLE.parents[2] / "mcp-config.json"
    assert set(json.loads(root_config.read_text())["mcpServers"]) == {"weather"}

    # This example reads only the explicit JSON file. Isolate credentials and saved settings.
    for key in list(os.environ):
        if "PARALLEL" in key.upper() and key != "PARALLEL_EXAMPLE_LIVE":
            monkeypatch.delenv(key)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("UPSTREAM_HEADERS", raising=False)
    monkeypatch.delenv("SYSTEM_PROMPT", raising=False)
    monkeypatch.chdir(tmp_path)

    async def no_update_check(*args, **kwargs):
        return None

    monkeypatch.setattr(lifecycle, "check_for_updates", no_update_check)
    observed = []
    original_send = httpx.AsyncClient.send

    async def record_send(client, request, *args, **kwargs):
        if request.url.path == "/mcp" and request.method == "POST":
            observed.append(
                {"url": str(request.url), "headers": dict(request.headers), "body": json.loads(request.content)}
            )
        return await original_send(client, request, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", record_send)
    with http_fixture(MCPFixture) as mcp_url, http_fixture(OllamaFixture) as ollama_url:
        live = os.getenv("PARALLEL_EXAMPLE_LIVE") == "1"
        selected_config = EXAMPLE
        if not live:
            # Only substitute the endpoint for offline protocol validation.
            config["mcpServers"]["parallel"]["url"] = mcp_url + "/mcp"
            selected_config = tmp_path / "mcp-config.json"
            selected_config.write_text(json.dumps(config))
        monkeypatch.setattr(app.state, "config_file", str(selected_config), raising=False)
        monkeypatch.setattr(app.state, "ollama_url", ollama_url, raising=False)
        monkeypatch.setattr(app.state, "ollama_headers", {}, raising=False)
        monkeypatch.setattr(app.state, "system_prompt", None, raising=False)
        monkeypatch.setattr(app.state, "max_tool_rounds", None, raising=False)
        with TestClient(app) as client:
            assert set(lifecycle.mcp_manager.sessions) == {"parallel"}
            response = client.post(
                "/api/chat",
                json={"model": "fixture", "stream": False, "messages": [{"role": "user", "content": OBJECTIVE}]},
            )
            assert response.status_code == 200, response.text
            final = response.json()["message"]["content"]
            assert "asyncio" in final.lower()
            assert SOURCE_URL in final

    methods = [r["body"]["method"] for r in observed]
    assert "initialize" in methods and "tools/list" in methods
    calls = [r for r in observed if r["body"]["method"] == "tools/call"]
    assert [r["body"]["params"]["name"] for r in calls] == ["web_search", "web_fetch"]
    for request in observed:
        assert request["headers"]["user-agent"] == "ollama-mcp-bridge"
        assert "authorization" not in request["headers"]
        assert not any("api-key" in key for key in request["headers"])
