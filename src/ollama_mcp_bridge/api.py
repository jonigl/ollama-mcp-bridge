"""FastAPI application"""
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Body, status, Request
from fastapi.responses import JSONResponse
from loguru import logger
import httpx

from .lifecycle import lifespan, get_proxy_service
from .schemas import CHAT_EXAMPLE
from .utils import check_for_updates
from . import __version__


# Create FastAPI app
app = FastAPI(
    title="Ollama MCP Bridge",
    description="Simple API proxy server with Ollama REST API compatibility and MCP tool integration",
    version=__version__,
    lifespan=lifespan
)


@app.get("/health", summary="Health check", description="Check the health status of the MCP Proxy and Ollama server.")
async def health():
    """Health check endpoint."""
    proxy_service = get_proxy_service()
    if not proxy_service:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Services not initialized")

    health_info = await proxy_service.health_check()
    status_code = status.HTTP_200_OK if health_info["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=health_info)


@app.post("/api/chat", summary="Generate a chat completion", description="Transparent proxy to Ollama's /api/chat with MCP tool injection.")
async def chat(
    body: Dict[str, Any] = Body(..., example=CHAT_EXAMPLE)
):
    """Transparent proxy for Ollama's /api/chat, with MCP tool injection."""
    proxy_service = get_proxy_service()
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

@app.get("/version", summary="Version information", description="Get version information and check for updates.")
async def version():
    """Version information endpoint."""
    latest_version = await check_for_updates(__version__)

    return {
        "version": __version__,
        "latest_version": latest_version
    }

@app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
               summary="Transparent proxy", description="Transparent proxy to any Ollama endpoint.",
               include_in_schema=False)
async def proxy_to_ollama(
    request: Request,
    path_name: str
):
    """Transparent proxy for all other Ollama endpoints."""
    proxy_service = get_proxy_service()
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
