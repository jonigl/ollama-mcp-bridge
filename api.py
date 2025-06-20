"""FastAPI application"""
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Body, status, Request
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
import httpx
from mcp_manager import MCPManager
from utils import check_ollama_health_async, proxy_request

# Global manager - will be initialized in lifespan
mcp_manager: MCPManager = None


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """FastAPI lifespan events"""
    global mcp_manager

    # Get config from app state
    config_file = getattr(fastapi_app.state, 'config_file', 'mcp-config.json')
    ollama_url = getattr(fastapi_app.state, 'ollama_url', 'http://localhost:11434')

    # Initialize manager and load servers
    mcp_manager = MCPManager(ollama_url=ollama_url)
    await mcp_manager.load_servers(config_file)
    logger.success(f"Startup complete. Total tools available: {len(mcp_manager.all_tools)}")

    yield

    # Cleanup on shutdown
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
    """
    Health check endpoint.
    """
    ollama_healthy = await check_ollama_health_async(mcp_manager.ollama_url) if mcp_manager else False
    response = {
        "status": "healthy" if ollama_healthy else "degraded",
        "ollama_status": "running" if ollama_healthy else "not accessible",
        "tools": len(mcp_manager.all_tools) if mcp_manager else 0
    }
    status_code = status.HTTP_200_OK if ollama_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=response)


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
    """
    Transparent proxy for Ollama's /api/chat, with MCP tool injection.
    """
    if not mcp_manager:
        raise HTTPException(status_code=503, detail="MCP manager not initialized")
    if not await check_ollama_health_async(mcp_manager.ollama_url):
        raise HTTPException(status_code=503, detail="Ollama server not accessible")
    try:
        if body.get("stream", False):
            return StreamingResponse(
                mcp_manager.proxy_with_tools(endpoint="/api/chat", payload=body, stream=True),
                media_type="application/json"
            )
        else:
            return await mcp_manager.proxy_with_tools(endpoint="/api/chat", payload=body, stream=False)
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
    """
    Transparent proxy for all other Ollama endpoints.
    """
    if not mcp_manager:
        raise HTTPException(status_code=503, detail="MCP manager not initialized")
    
    return await proxy_request(
        target_url=mcp_manager.ollama_url,
        request=request,
        path=path_name,
        check_health=True,
        ollama_url=mcp_manager.ollama_url
    )
