<p align="center">

  <img src="./misc/ollama-mcp-bridge-logo-512.png" width="256" />
</p>
<p align="center">
<i>An API service that bridges multiple Model Context Protocol (MCP) servers with Ollama, providing unified access to tools across all connected servers for enhanced AI model interactions.</i>
</p>

# Ollama MCP Bridge

[![Tests](https://github.com/jonigl/ollama-mcp-bridge/actions/workflows/test.yml/badge.svg)](https://github.com/jonigl/ollama-mcp-bridge/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## Features

- 🏗️ **Modular Architecture**: Clean separation into CLI, API, and MCP management modules
- 🚀 **Pre-loaded Servers**: All MCP servers are connected at startup from JSON configuration
- 🛠️ **All Tools Available**: Ollama can use any tool from any connected server simultaneously
- ⚡️ **FastAPI Backend**: Modern async API with automatic documentation
- 💻 **Typer CLI**: Clean command-line interface with configurable options
- 📊 **Structured Logging**: Uses loguru for comprehensive logging
- 🔧 **Configurable Ollama**: Specify custom Ollama server URL via CLI
- 🔗 **Tool Integration**: Automatic tool call processing and response integration
- 📝 **JSON Configuration**: Configure multiple servers with complex commands and environments


## Requirements

- Python >= 3.10.15
- Ollama server running (local or remote)
- MCP server scripts configured in mcp-config.json

## Installation

```bash
# Clone the repository
git clone https://github.com/jonigl/ollama-mcp-bridge.git
cd ollama-mcp-bridge

# Install dependencies using uv
uv sync

# Start Ollama (if not already running)
ollama serve

# Run the bridge
python main.py
```

## How It Works

1. **Startup**: All MCP servers defined in the configuration are loaded and connected
2. **Tool Collection**: Tools from all servers are collected and made available to Ollama
3. **Chat Completion Request**: When a chat completion request is received:
  - The request is forwarded to Ollama along with the list of all available tools
  - If Ollama chooses to invoke any tools, those tool calls are executed through the corresponding MCP servers
   - Tool responses are fed back to Ollama
   - The final response (with tool results integrated) is returned to the client
4. **Logging**: All operations are logged using loguru for debugging and monitoring

## Configuration

Create an MCP configuration file (`mcp-config.json`) with your servers:

```json
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": [
        "--directory",
        ".",
        "run",
        "mock-weather-mcp-server.py"
      ],
      "env": {
        "MCP_LOG_LEVEL": "ERROR"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/tmp"
      ]
    }
  }
}
```

## Usage

### Start the Server
```bash
# Start with default settings (config: mcp-config.json, host: localhost, port: 8000)
python main.py

# Start with custom configuration file
python main.py --config /path/to/custom-config.json

# Custom host and port
python main.py --host 0.0.0.0 --port 8080

# Custom Ollama server URL
python main.py --ollama-url http://192.168.1.100:11434

# Combine options
python main.py --config custom.json --host 0.0.0.0 --port 8080 --ollama-url http://remote-ollama:11434
```

> [!TIP]
> This bridge supports both streaming responses and thinking mode. You receive incremental responses as they are generated, with tool calls and intermediate thinking messages automatically proxied between Ollama and all connected MCP tools.

### CLI Options
- `--config`: Path to MCP configuration file (default: `mcp-config.json`)
- `--host`: Host to bind the server (default: `localhost`)
- `--port`: Port to bind the server (default: `8000`)
- `--ollama-url`: Ollama server URL (default: `http://localhost:11434`)

### API Usage

The API is available at `http://localhost:8000`.

- **Swagger UI docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Ollama-compatible endpoints:**
  - `POST /api/chat` — Chat endpoint (same as Ollama API, but with MCP tool support)
- **Health check:**
  - `GET /health`

This bridge acts as a drop-in proxy for the Ollama API, but with all MCP tools from all connected servers available to every request. You can use your existing Ollama clients and libraries, just point them to this bridge instead of your Ollama server.

### Example: Chat
```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3:0.6b",
    "messages": [{"role": "user", "content": "What tools are available?"}]
  }'
```

> [!TIP]
> Use `/docs` for interactive API exploration and testing.

## Architecture

The application is structured into three main modules:

### `main.py` - CLI Entry Point
- Uses Typer for command-line interface
- Handles configuration and server startup
- Passes configuration to FastAPI app

### `api.py` - FastAPI Application
- Defines API endpoints (`/api/chat`, `/health`)
- Manages application lifespan (startup/shutdown)
- Handles HTTP request/response processing

### `mcp_manager.py` - MCP Management
- Loads and manages MCP servers
- Collects and exposes all available tools
- Handles tool calls and integrates results into Ollama responses

### `utils.py` - Utility Functions
- NDJSON parsing, health checks, and other helper functions

## Development

### Project Structure
```
├── main.py                     # CLI entry point (Typer)
├── api.py                      # FastAPI application and endpoints
├── mcp_manager.py              # MCP server management and tool handling
├── utils.py                    # Utility functions (NDJSON parsing, health checks, etc.)
├── mcp-config.json             # MCP server configuration
├── pyproject.toml              # Project configuration and dependencies (uv)
├── uv.lock                     # uv lock file
├── test_unit.py                # Unit tests (GitHub Actions compatible)
├── test_api.py                 # Integration tests (require running server)
├── .github/workflows/test.yml  # GitHub Actions CI pipeline
├── mock-weather-mcp-server.py  # Example MCP server for testing
└── README.md                   # This file
```

### Key Dependencies
- **FastAPI**: Modern web framework for the API
- **Typer**: CLI framework for command-line interface
- **loguru**: Structured logging throughout the application
- **ollama**: Python client for Ollama communication
- **mcp**: Model Context Protocol client library
- **pytest**: Testing framework for API validation

### Testing

The project has two types of tests:

#### Unit Tests (GitHub Actions compatible)
```bash
# Install test dependencies
uv sync --extra test

# Run unit tests (no server required)
uv run pytest test_unit.py -v
```

These tests check:
- Configuration file loading
- Module imports and initialization
- Project structure
- Tool definition formats

#### Integration Tests (require running services)
```bash
# First, start the server in one terminal
uv run python main.py

# Then in another terminal, run the integration tests
uv run pytest test_api.py -v
```

These tests check:
- API endpoints with real HTTP requests
- End-to-end functionality with Ollama
- Tool calling and response integration

#### Manual Testing
```bash
# Quick manual test with curl (server must be running)
curl -X GET "http://localhost:8000/health"

curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3:0.6b", "messages": [{"role": "user", "content": "What tools are available?"}]}'
```

> [!NOTE]
> Tests require the server to be running on localhost:8000. Make sure to start the server before running pytest.



This creates a seamless experience where Ollama can use any tool from any connected MCP server without the client needing to know about the underlying MCP infrastructure.

## Inspiration and Credits

This project is based on the basic MCP client from my Medium article: [Build an MCP Client in Minutes: Local AI Agents Just Got Real](https://medium.com/@jonigl/build-an-mcp-client-in-minutes-local-ai-agents-just-got-real-a10e186a560f).

The inspiration to create this simple bridge came from this GitHub issue: [jonigl/mcp-client-for-ollama#22](https://github.com/jonigl/mcp-client-for-ollama/issues/22), suggested by [@nyomen](https://github.com/nyomen).

---

Made with ❤️ by [jonigl](https://github.com/jonigl)
