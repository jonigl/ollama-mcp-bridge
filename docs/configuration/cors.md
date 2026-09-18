# CORS

Cross-Origin Resource Sharing is configured with the `CORS_ORIGINS` environment
variable, so browser-based frontends can call the bridge directly.

```bash
# Allow all origins — the default
ollama-mcp-bridge

# One origin
CORS_ORIGINS="http://localhost:3000" ollama-mcp-bridge

# Several, comma-separated
CORS_ORIGINS="http://localhost:3000,http://localhost:8080,https://app.example.com" \
  ollama-mcp-bridge
```

The configuration is logged at startup: the allowed origins when they're set, and a
warning when they aren't.

!!! warning "Don't ship `*`"

    The default `CORS_ORIGINS="*"` allows every origin. It's convenient for local
    development and wrong for anything exposed beyond your machine — list exact origins
    in production.
