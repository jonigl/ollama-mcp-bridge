"""FastAPI application"""

from typing import Dict, Any
import httpx
from fastapi import FastAPI, HTTPException, Body, status, Request
from fastapi.responses import JSONResponse, Response
from starlette.requests import ClientDisconnect
from loguru import logger

from .lifecycle import lifespan, get_proxy_service
from .schemas import CHAT_EXAMPLE
from .utils import ClientDisconnected, check_for_updates, configure_cors, run_until_client_disconnects
from . import __version__

# Goes nowhere: the client is gone. 499 is nginx's "client closed request" convention.
CLIENT_CLOSED_REQUEST = 499

# Create FastAPI app
app = FastAPI(
    title="Ollama MCP Bridge",
    description="Simple API proxy server with Ollama REST API compatibility and MCP tool integration",
    version=__version__,
    lifespan=lifespan,
)

# Configure CORS middleware
configure_cors(app)


@app.get("/health", summary="Health check", description="Check the health status of the MCP Proxy and Ollama server.")
async def health():
    """Health check endpoint."""
    proxy_service = get_proxy_service()
    if not proxy_service:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Services not initialized")

    health_info = await proxy_service.health_check()
    status_code = status.HTTP_200_OK if health_info["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=health_info)


@app.post(
    "/api/chat",
    summary="Generate a chat completion",
    description="Transparent proxy to Ollama's /api/chat with MCP tool injection.",
)
async def chat(request: Request, body: Dict[str, Any] = Body(..., example=CHAT_EXAMPLE)):
    """Transparent proxy for Ollama's /api/chat, with MCP tool injection."""
    proxy_service = get_proxy_service()
    if not proxy_service:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Services not initialized")

    try:
        if body.get("stream", False):
            # Starlette owns the receive channel while streaming and already cancels the
            # response generator on disconnect, so the watcher has to stay out of the way
            return await proxy_service.proxy_chat_with_tools(body, stream=True)

        # Buffered: nothing cancels this long await when the client leaves, hence the watcher
        return await run_until_client_disconnects(proxy_service.proxy_chat_with_tools(body, stream=False), request)
    except ClientDisconnected:
        logger.info("/api/chat: client disconnected, aborted the request to Ollama")
        return Response(status_code=CLIENT_CLOSED_REQUEST)
    except httpx.HTTPStatusError as e:
        logger.error(f"/api/chat failed: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text) from e
    except httpx.RequestError as e:
        logger.error(f"/api/chat connection error: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Could not connect to Ollama server: {str(e)}") from e
    except Exception as e:
        logger.error(f"/api/chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"/api/chat failed: {str(e)}") from e


@app.get("/version", summary="Version information", description="Get version information and check for updates.")
async def version():
    """Version information endpoint."""
    latest_version = await check_for_updates(__version__)

    return {"version": __version__, "latest_version": latest_version}


@app.api_route(
    "/{path_name:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    summary="Transparent proxy",
    description="Transparent proxy to any Ollama endpoint.",
    include_in_schema=False,
)
async def proxy_to_ollama(request: Request, path_name: str):
    """Transparent proxy for all other Ollama endpoints."""
    proxy_service = get_proxy_service()
    if not proxy_service:
        raise HTTPException(status_code=503, detail="Services not initialized")

    try:
        # Must happen before the watcher starts polling the receive channel
        await request.body()

        # This path always buffers, even for stream=true, so the watcher always applies here.
        # If it ever streams, exclude it like /api/chat does: starlette owns the channel then.
        return await run_until_client_disconnects(proxy_service.proxy_generic_request(path_name, request), request)
    # ClientDisconnect is starlette's, raised if the client leaves mid-upload; ClientDisconnected
    # is ours, raised by the watcher. Same outcome: stop working for a client that is gone.
    except (ClientDisconnect, ClientDisconnected):
        logger.info(f"/{path_name}: client disconnected, aborted the request to Ollama")
        return Response(status_code=CLIENT_CLOSED_REQUEST)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text) from e
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Could not connect to Ollama server: {str(e)}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy request failed: {str(e)}") from e
