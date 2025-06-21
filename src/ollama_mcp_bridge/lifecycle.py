"""Application lifecycle management for FastAPI"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger

from .mcp_manager import MCPManager
from .proxy_service import ProxyService

# Global services that will be initialized in lifespan
mcp_manager: MCPManager = None
proxy_service: ProxyService = None


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """FastAPI lifespan events"""
    global mcp_manager, proxy_service

    try:
        # Get config from app state with explicit defaults
        config_file = getattr(fastapi_app.state, 'config_file', 'mcp-config.json')
        ollama_url = getattr(fastapi_app.state, 'ollama_url', 'http://localhost:11434')

        logger.info(f"Starting with config file: {config_file}, Ollama URL: {ollama_url}")

        # Initialize manager and load servers
        mcp_manager = MCPManager(ollama_url=ollama_url)
        await mcp_manager.load_servers(config_file)

        # Initialize services
        proxy_service = ProxyService(mcp_manager)

        logger.success(f"Startup complete. Total tools available: {len(mcp_manager.all_tools)}")
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        # Reset globals on failed startup
        mcp_manager = None
        proxy_service = None
        raise

    yield

    # Cleanup on shutdown
    logger.info("Shutting down services...")
    try:
        if proxy_service:
            await proxy_service.cleanup()
    except Exception as e:
        logger.error(f"Error during proxy service cleanup: {str(e)}")

    try:
        if mcp_manager:
            await mcp_manager.cleanup()
    except Exception as e:
        logger.error(f"Error during MCP manager cleanup: {str(e)}")

    # Reset globals
    mcp_manager = None
    proxy_service = None
    logger.info("Shutdown complete")


def get_mcp_manager() -> MCPManager:
    """Get the global MCP manager instance."""
    return mcp_manager


def get_proxy_service() -> ProxyService:
    """Get the global proxy service instance."""
    return proxy_service
