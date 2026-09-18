# MCP servers

MCP servers are declared under `mcpServers` in your config file — `mcp-config.json` by
default, or whatever you pass to [`--config`](cli.md#-config).

## Transports

You don't choose a transport explicitly. The bridge infers it from the shape of the entry:

| Config contains | Transport |
| --- | --- |
| `command` | **stdio** — a local process the bridge spawns |
| `url` ending in `/sse` | **SSE** — Server-Sent Events |
| any other `url` | **StreamableHTTP** |

## A full example

```json title="mcp-config.json"
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": ["--directory", "./mock-weather-mcp-server", "run", "main.py"],
      "env": {
        "MCP_LOG_LEVEL": "ERROR"
      },
      "toolFilter": {
        "mode": "include",
        "tools": ["get_current_temperature", "get_forecast"]
      }
    },
    "remote_streamable_http": {
      "url": "https://example.com/mcp"
    },
    "remote_sse": {
      "url": "https://example.com/sse"
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "toolFilter": {
        "mode": "exclude",
        "tools": ["delete_file", "write_file"]
      }
    }
  }
}
```

## Fields

`command` / `args` / `env`
:   For stdio servers: the executable to run, its arguments, and extra environment
    variables for the child process.

`url`
:   For remote servers. The suffix decides between SSE and StreamableHTTP.

`headers`
:   Optional headers sent to a remote MCP server. Supports
    [variable expansion](variable-expansion.md), so secrets can come from the
    environment rather than the file.

`toolFilter`
:   Optional allow-list or deny-list of tool names — see
    [Tool filtering](tool-filtering.md).

## How tools are named

Tools from every server land in one flat list, namespaced as `<server>.<tool>`. A
`get_forecast` tool on the `weather` server is offered to the model as
`weather.get_forecast`. The bridge keeps the original server and tool name alongside it,
so dispatch back to the right server is unambiguous even when two servers expose the same
tool name.

## Relative paths

!!! important "Paths resolve against the config file"

    Every relative path in the config is interpreted relative to **the directory holding
    the config file**, not the process working directory. The bridge sets each server's
    `cwd` accordingly, and that same directory is what
    [`${workspaceFolder}`](variable-expansion.md) expands to.

    This means you can keep a config and its servers in one folder and run the bridge
    from anywhere.

## One bad server won't stop startup

Each server is connected inside its own exit stack, which is only merged into the
bridge's on success. A server that fails to start is logged and skipped — the rest still
come up, and the bridge serves whatever tools it managed to collect.
