# Installation

## Requirements

- Python **3.10** or newer
- An **Ollama server** running, local or remote
- An **MCP configuration file** with at least one server defined — see
  [MCP servers](../configuration/mcp-servers.md)

## Install

=== "uv tool"

    Installs it once as a standalone tool, on its own isolated environment, and
    puts `ollama-mcp-bridge` on your PATH. The same command upgrades it later.

    ```bash
    uv tool install --upgrade ollama-mcp-bridge
    ```

    Then run it:

    ```bash
    ollama-mcp-bridge
    ```

=== "pip"

    ```bash
    pip install --upgrade ollama-mcp-bridge
    ```

    Then run it:

    ```bash
    ollama-mcp-bridge
    ```

=== "Docker"

    Pre-built multi-arch images are published on every release. See
    [Docker](docker.md) for the full set of flags and Compose usage.

    ```bash
    docker compose up
    ```

=== "From source"

    ```bash
    git clone https://github.com/jonigl/ollama-mcp-bridge.git
    cd ollama-mcp-bridge

    # Start Ollama if it isn't running yet
    ollama serve

    uv run ollama-mcp-bridge
    ```

    For development, install it in editable mode so the `ollama-mcp-bridge`
    command tracks your working tree:

    ```bash
    uv tool install --editable .
    ollama-mcp-bridge
    ```

=== "uvx (no install)"

    Runs the latest published version without adding anything to your environment.
    It still expects an `mcp-config.json` in the directory you run it from —
    see [Quick start](quickstart.md).

    ```bash
    uvx ollama-mcp-bridge
    ```

    !!! tip

        With `uvx` you always invoke it as `uvx ollama-mcp-bridge`, not as a bare
        `ollama-mcp-bridge`. Every example in these docs applies either way.

## Check the install

```bash
ollama-mcp-bridge --version
```

This prints the installed version and checks PyPI for a newer one. The same check runs
at startup and on the [`/version`](../guide/api.md#get-version) endpoint.
