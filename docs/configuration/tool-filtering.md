# Tool filtering

By default every tool a server exposes is offered to the model. `toolFilter` narrows
that, per server.

```json
"toolFilter": {
  "mode": "include",
  "tools": ["get_current_temperature", "get_forecast"]
}
```

`mode`
:   Either `"include"` (allow-list) or `"exclude"` (deny-list). Defaults to `"include"`
    when omitted.

`tools`
:   Array of exact tool names. Matching is **case-sensitive**.

## Behaviour

- No `toolFilter`, or an empty `tools` array → all tools are loaded.
- **Include mode** → only the listed tools are exposed. A listed tool that the server
  doesn't have logs a warning; the connection continues.
- **Exclude mode** → everything except the listed tools is exposed.
- An invalid `mode` value stops the bridge at startup with an error.

!!! warning "An invalid mode is fatal"

    Unlike a failing server, a malformed `toolFilter` isn't skipped — it exits with
    status 1. This is deliberate: silently ignoring a broken deny-list would expose tools
    you meant to block.

## Examples

=== "Include (default mode)"

    Only these two tools reach the model.

    ```json
    {
      "mcpServers": {
        "weather": {
          "command": "uv",
          "args": ["--directory", "./mock-weather-mcp-server", "run", "main.py"],
          "toolFilter": {
            "tools": ["get_current_temperature", "get_forecast"]
          }
        }
      }
    }
    ```

=== "Mixed modes"

    An allow-list on one server, a deny-list on another.

    ```json
    {
      "mcpServers": {
        "weather": {
          "command": "uv",
          "args": ["--directory", "./mock-weather-mcp-server", "run", "main.py"],
          "toolFilter": {
            "mode": "include",
            "tools": ["get_current_temperature"]
          }
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
