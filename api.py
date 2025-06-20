"""FastAPI application"""
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Body, status, Request
from fastapi.responses import JSONResponse
from loguru import logger
import httpx

from mcp_manager import MCPManager
from services.proxy_service import ProxyService

# Global services - will be initialized in lifespan
mcp_manager: MCPManager = None
proxy_service: ProxyService = None


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """FastAPI lifespan events"""
    global mcp_manager, proxy_service

    # Get config from app state
    config_file = getattr(fastapi_app.state, 'config_file', 'mcp-config.json')
    ollama_url = getattr(fastapi_app.state, 'ollama_url', 'http://localhost:11434')

    # Initialize manager and load servers
    mcp_manager = MCPManager(ollama_url=ollama_url)
    await mcp_manager.load_servers(config_file)

    # Initialize services
    proxy_service = ProxyService(mcp_manager)

    logger.success(f"Startup complete. Total tools available: {len(mcp_manager.all_tools)}")

    yield

    # Cleanup on shutdown
    if proxy_service:
        await proxy_service.cleanup()
    if mcp_manager:
        await mcp_manager.cleanup()


# Create FastAPI app
app = FastAPI(
    title="Ollama MCP Bridge",
    description="Simple API proxy for Ollama's REST API with MCP tool integration",
    version="0.2.0",
    lifespan=lifespan
)


@app.get("/health", summary="Health check", description="Check the health status of the MCP Proxy and Ollama server.")
async def health():
    """Health check endpoint."""
    if not proxy_service:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Services not initialized")

    health_info = await proxy_service.health_check()
    status_code = status.HTTP_200_OK if health_info["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=health_info)


@app.post("/api/chat", summary="Generate a chat completion", description="Transparent proxy to Ollama's /api/chat with MCP tool injection.")
async def chat(
    body: Dict[str, Any] = Body(..., examples={
        "model": "qwen3:0.6b",
        "messages": [
            {"role": "system", "content": "You are a weather assistant."},
            {"role": "user", "content": "What's the weather like in Paris today?"}
        ],
        "think": True,
        "stream": False,
        "format": None,
        "options": {"temperature": 0.7, "top_p": 0.9}
    })
):
    """Transparent proxy for Ollama's /api/chat, with MCP tool injection."""
    if not proxy_service:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Services not initialized")

    try:
        return await proxy_service.proxy_chat_with_tools(body, stream=body.get("stream", False))
    except httpx.HTTPStatusError as e:
        logger.error(f"/api/chat failed: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text) from e
    except httpx.RequestError as e:
        logger.error(f"/api/chat connection error: {str(e)}")
        raise HTTPException(status_code=503,
                           detail=f"Could not connect to Ollama server: {str(e)}") from e
    except Exception as e:
        logger.error(f"/api/chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"/api/chat failed: {str(e)}") from e


@app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
               summary="Transparent proxy", description="Transparent proxy to any Ollama endpoint.")
async def proxy_to_ollama(
    request: Request,
    path_name: str
):
    """Transparent proxy for all other Ollama endpoints."""
    if not proxy_service:
        raise HTTPException(status_code=503, detail="Services not initialized")

    try:
        return await proxy_service.proxy_generic_request(path_name, request)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text) from e
    except httpx.RequestError as e:
        raise HTTPException(status_code=503,
                           detail=f"Could not connect to Ollama server: {str(e)}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy request failed: {str(e)}") from e
