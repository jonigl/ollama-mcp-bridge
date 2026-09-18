# Variable expansion

Any string value in the config file supports two substitutions.

`${workspaceFolder}`
:   The directory containing the config file. See
    [relative paths](mcp-servers.md#relative-paths).

`${env:VAR_NAME}`
:   The value of that environment variable.

Together they keep machine-specific paths and secrets out of the file itself, which
means the config can be committed.

```json title="mcp-config.json"
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "${workspaceFolder}/data"
      ]
    },
    "remote_with_headers": {
      "url": "https://example.com/mcp",
      "headers": {
        "X-Client-Name": "ollama-mcp-bridge",
        "X-Request-Tag": "${env:MCP_REQUEST_TAG}"
      }
    }
  }
}
```

!!! tip

    `${env:...}` is the right place for API keys on remote MCP servers. For credentials
    aimed at whatever sits between the bridge and *Ollama*, use
    [upstream headers](cli.md#-upstream-header) instead — those are a different hop.
