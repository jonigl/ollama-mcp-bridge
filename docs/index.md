---
title: MCP tools for every Ollama client
template: home.html
hide:
  - navigation
  - toc
---

## What it does

The bridge sits in front of your Ollama server and speaks the same API. Every endpoint
behaves identically except [`/api/chat`](guide/api.md), which injects the tools from all
connected MCP servers and runs the tool-calling loop server-side.

Your client never sees the loop. It sends one chat request and gets one answer back — with
tool results already folded in, streamed in real time.

<div class="grid cards" markdown>

-   :material-power-plug:{ .lg .middle } __Drop-in replacement__

    ---

    Same endpoints, same payloads. Change the host your Ollama client points at and
    nothing else. Existing SDKs and libraries keep working.

    [:octicons-arrow-right-24: API reference](guide/api.md)

-   :material-transit-connection-variant:{ .lg .middle } __Any MCP transport__

    ---

    Local processes over stdio, remote servers over StreamableHTTP or SSE. The transport
    is inferred from the config — you just declare the server.

    [:octicons-arrow-right-24: Configure servers](configuration/mcp-servers.md)

-   :material-refresh-auto:{ .lg .middle } __Multi-round tool calling__

    ---

    The bridge loops until the model stops asking for tools, then returns the final
    answer. Cap it with `--max-tool-rounds` when you want a ceiling.

    [:octicons-arrow-right-24: How it works](guide/how-it-works.md)

-   :material-filter-variant:{ .lg .middle } __Per-server tool filtering__

    ---

    Allow-list or deny-list the tools each server exposes, so the model only sees what
    you want it to reach for.

    [:octicons-arrow-right-24: Tool filtering](configuration/tool-filtering.md)

-   :material-cloud-outline:{ .lg .middle } __Local and cloud models__

    ---

    Point it at a local Ollama, a remote one, or Ollama's cloud models. Add upstream
    headers when there's a gateway or auth layer in between.

    [:octicons-arrow-right-24: CLI options](configuration/cli.md)

-   :material-docker:{ .lg .middle } __Runs anywhere__

    ---

    `uvx`, `pip`, or pre-built multi-arch Docker images for `linux/amd64` and
    `linux/arm64` published on every release.

    [:octicons-arrow-right-24: Docker](getting-started/docker.md)

</div>

## Get running in a minute

=== "uvx"

    ```bash
    uvx ollama-mcp-bridge
    ```

=== "pip"

    ```bash
    pip install --upgrade ollama-mcp-bridge
    ollama-mcp-bridge
    ```

=== "Docker"

    ```bash
    docker run -p 8000:8000 \
      -e OLLAMA_URL=http://host.docker.internal:11434 \
      -v "$PWD/mcp-config.json:/mcp-config.json" \
      -w / \
      ghcr.io/jonigl/ollama-mcp-bridge:latest
    ```

You'll need an [`mcp-config.json`](configuration/mcp-servers.md) with at least one server
in it, and an Ollama server running.

[Full quick start :octicons-arrow-right-24:](getting-started/quickstart.md){ .md-button .md-button--primary }
[Installation options :octicons-arrow-right-24:](getting-started/installation.md){ .md-button }

## Related projects

- [**MCP Client for Ollama**](https://github.com/jonigl/mcp-client-for-ollama) — a TUI client
  for MCP servers with Ollama. Multi-server support, model switching, streaming, tool
  management, human-in-the-loop, thinking mode and saved preferences.
- [**simple-ollama-chat**](https://github.com/jonigl/simple-ollama-chat) — a small chat UI
  that works with the bridge, handy for exercising tool-augmented models quickly.

## Credits

Based on the basic MCP client from
[Build an MCP Client in Minutes: Local AI Agents Just Got Real](https://medium.com/@jonigl/build-an-mcp-client-in-minutes-local-ai-agents-just-got-real-a10e186a560f).
The idea came from [jonigl/mcp-client-for-ollama#22](https://github.com/jonigl/mcp-client-for-ollama/issues/22),
suggested by [@nyomen](https://github.com/nyomen).
