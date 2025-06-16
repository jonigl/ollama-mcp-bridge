"""Simple CLI entry point for MCP Proxy"""
import typer
import uvicorn
from loguru import logger

from api import app


def cli_app(
    config: str = typer.Option("mcp-config.json", "--config", help="Path to MCP config JSON file"),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", help="Port to bind to"),
    ollama_url: str = typer.Option("http://localhost:11434", "--ollama-url", help="Ollama server URL"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload")
):
    """Start the MCP proxy server"""
    # Store config in app state so lifespan can access it
    app.state.config_file = config
    app.state.ollama_url = ollama_url
    
    logger.info(f"Starting MCP proxy server on {host}:{port}")
    logger.info(f"Using Ollama server: {ollama_url}")
    logger.info(f"Using config file: {config}")
    
    # Start the server
    uvicorn.run("api:app", host=host, port=port, reload=reload)

def main():
    typer.run(cli_app)

if __name__ == "__main__":
    main()
