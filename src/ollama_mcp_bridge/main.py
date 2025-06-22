"""Simple CLI entry point for MCP Proxy"""
import asyncio
import typer
import uvicorn
from loguru import logger

from .api import app
from .utils import check_ollama_health, check_for_updates, validate_cli_inputs
from . import __version__

def cli_app(
    config: str = typer.Option("mcp-config.json", "--config", help="Path to MCP config JSON file"),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", help="Port to bind to"),
    ollama_url: str = typer.Option("http://localhost:11434", "--ollama-url", help="Ollama server URL"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
    version: bool = typer.Option(False, "--version", help="Show version information, check for updates and exit"),
):
    """Start the API proxy server with Ollama REST API compatibility and MCP tool integration"""
    if version:
        typer.echo(f"{typer.style('ollama-mcp-bridge', fg=typer.colors.BRIGHT_YELLOW, bold=True)} {typer.style('v'+__version__, fg=typer.colors.BRIGHT_CYAN, bold=True)}")
        # Check for updates and print if available
        asyncio.run(check_for_updates(__version__, print_message=True))
        raise typer.Exit(0)
    validate_cli_inputs(config, host, port, ollama_url)
    # Store config in app state so lifespan can access it
    app.state.config_file = config
    app.state.ollama_url = ollama_url

    logger.info(f"Starting MCP proxy server on {host}:{port}")
    logger.info(f"Using Ollama server: {ollama_url}")
    logger.info(f"Using config file: {config}")

    # Check for updates (messages will be logged automatically)
    asyncio.run(check_for_updates(__version__))

    # Check Ollama server health before starting
    if not check_ollama_health(ollama_url):
        logger.info("Please ensure Ollama is running with: ollama serve")
        raise typer.Exit(1)

    # Start the server
    logger.info("API endpoints:")
    logger.info("  • POST /api/chat - Ollama-compatible chat with MCP tools")
    logger.info("  • GET /{path_name} - Transparent proxy to any Ollama endpoint")
    logger.info("  • GET /health - Health check and status")
    logger.info("  • GET /version - Version information and update check")
    logger.info("  • GET /docs - Swagger UI (API documentation)")
    uvicorn.run("ollama_mcp_bridge.api:app", host=host, port=port, reload=reload)

def main():
    """Main entry point for the CLI application"""
    typer.run(cli_app)

if __name__ == "__main__":
    main()
