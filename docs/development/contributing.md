# Contributing

Contributions are welcome. `CONTRIBUTING.md` in the repository root is the authoritative
version of this; what follows is the short form.

## Setup

```bash
git clone https://github.com/jonigl/ollama-mcp-bridge.git
cd ollama-mcp-bridge

uv sync            # installs dependencies, including the dev group
```

Dependency management is [uv](https://github.com/astral-sh/uv). The package installs from
a `src/` layout, and the version comes from git tags via `hatch-vcs`.

!!! danger "Never edit `_version.py`"

    `src/ollama_mcp_bridge/_version.py` is generated at build time from the git tag. Any
    edit to it will be overwritten.

## Running locally

```bash
uv run ollama-mcp-bridge --config mcp-config.json --port 8000
```

The repository's default `mcp-config.json` launches `mock-weather-mcp-server/`, a small
FastMCP stdio server, so the bridge can be exercised without any external MCP server.

## Formatting

[Black](https://black.readthedocs.io/), line length **120**.

```bash
black .                              # format
uv run black --check src/ tests/     # what CI checks
```

## Commits

[Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`,
`style:`, `refactor:`, `test:`, `chore:`.

## Releasing

- Pushing a `vX.Y.Z` tag publishes to **TestPyPI**
- Creating a GitHub Release publishes to **PyPI**

See `CI.md` for the details.
