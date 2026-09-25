---
title: "Run with Docker and Docker Compose"
description: "Run Ollama MCP Bridge from the multi-arch GHCR image (amd64, arm64) with Docker or Docker Compose, and make MCP server commands work inside the container."
---

# Docker

Pre-built multi-arch images for `linux/amd64` and `linux/arm64` are published to the
[GitHub Container Registry](https://github.com/jonigl/ollama-mcp-bridge/pkgs/container/ollama-mcp-bridge)
on every release.

| Tag | What it points at |
| --- | --- |
| `latest` | Most recent stable release |
| `vX.Y.Z` | A specific version, e.g. `v0.10.0` |
| `sha-<commit>` | The build for an exact commit |

## Docker Compose

```bash
docker compose up
```

The bundled `docker-compose.yml`:

- builds the bridge from source using the `Dockerfile`
- connects to Ollama on the host via `host.docker.internal:11434`
- mounts `./mcp-config.json`, which includes the mock weather server
- exposes port `8000`
- allows all CORS origins, configurable with [`CORS_ORIGINS`](../configuration/cors.md)
- supports [`OLLAMA_PROXY_TIMEOUT`](../configuration/environment.md#ollama_proxy_timeout)

!!! tip "Skip the local build"

    To use the pre-built image instead of building, replace the `build:` block in
    `docker-compose.yml` with:

    ```yaml
    image: ghcr.io/jonigl/ollama-mcp-bridge:latest
    ```

## Docker without Compose

```bash
docker run -p 8000:8000 \
  -e OLLAMA_URL=http://host.docker.internal:11434 \
  -v "$PWD/mcp-config.json:/mcp-config.json" \
  -v "$PWD/mock-weather-mcp-server:/mock-weather-mcp-server" \
  -w / \
  ghcr.io/jonigl/ollama-mcp-bridge:latest
```

What each flag is doing:

`-p 8000:8000`
:   Exposes the bridge on the host at port `8000`.

`-e OLLAMA_URL=http://host.docker.internal:11434`
:   Routes Ollama traffic to the host machine. Required on macOS and Windows.

`-v "$PWD/mcp-config.json:/mcp-config.json"`
:   Mounts your config into the container.

`-v "$PWD/mock-weather-mcp-server:/mock-weather-mcp-server"`
:   Mounts the mock MCP server **without** `:ro`, so `uv` can create its `.venv`
    inside the directory.

`-w /`
:   Sets the working directory to `/` so relative paths in `mcp-config.json` resolve
    correctly.

!!! note "On Linux"

    `host.docker.internal` may not resolve. Use `--network host` with
    `OLLAMA_URL=http://localhost:11434`, or substitute your host's LAN IP.

## MCP servers inside containers

Commands in your config run *inside the container*, so they have to exist there.

:material-check: Works
:   `npx` for Node-based MCP servers, `uvx` for Python ones, and any executable present
    in the image.

:material-close: Doesn't work
:   `docker` commands, unless you've set up Docker-in-Docker. Paths that only exist on
    your host machine.
