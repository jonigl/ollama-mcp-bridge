"""Utility functions for ollama-mcp-bridge"""
import httpx
import json
from loguru import logger
from fastapi import Request, Response, HTTPException
from typing import Optional


def check_ollama_health(ollama_url: str, timeout: int = 3) -> bool:
    """Check if Ollama server is running and accessible (sync version for CLI)."""
    try:
        resp = httpx.get(f"{ollama_url}/api/tags", timeout=timeout)
        if resp.status_code == 200:
            logger.success("✓ Ollama server is accessible")
            return True
        logger.error(f"Ollama server not accessible at {ollama_url}")
        return False
    except Exception as e:
        logger.error(f"Failed to connect to Ollama: {e}")
        return False

async def check_ollama_health_async(ollama_url: str, timeout: int = 3) -> bool:
    """Check if Ollama server is running and accessible (async version for FastAPI)."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{ollama_url}/api/tags", timeout=timeout)
            if resp.status_code == 200:
                return True
            logger.error(f"Ollama server not accessible at {ollama_url}")
            return False
    except Exception as e:
        logger.error(f"Failed to connect to Ollama: {e}")
        return False

async def iter_ndjson_chunks(chunk_iterator):
    """Async generator that yields parsed JSON objects from NDJSON (newline-delimited JSON) byte chunks."""
    buffer = b""
    async for chunk in chunk_iterator:
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            if line.strip():
                try:
                    yield json.loads(line)
                except Exception as e:
                    logger.debug(f"Error parsing NDJSON line: {e}")
    # Handle any trailing data
    if buffer.strip():
        try:
            yield json.loads(buffer)
        except Exception as e:
            logger.debug(f"Error parsing trailing NDJSON: {e}")

async def proxy_request(
    target_url: str,
    request: Request,
    path: str,
    check_health: bool = True,
    ollama_url: Optional[str] = None
) -> Response:
    """
    Generic proxy function that forwards a request to a target URL and returns the response.
    
    Args:
        target_url: Base URL to forward the request to
        request: FastAPI Request object
        path: Path to append to the target URL
        check_health: Whether to check if the target is accessible first
        ollama_url: URL to check health against (if different from target_url)
    
    Returns:
        Response: FastAPI Response with the proxied content
    """
    # Check health if requested
    if check_health and ollama_url:
        if not await check_ollama_health_async(ollama_url):
            raise HTTPException(status_code=503, detail="Target server not accessible")
    
    try:
        # Create URL to forward to
        url = f"{target_url}/{path}"
        
        # Copy headers but exclude host
        headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
        
        # Get request body if present
        body = await request.body()
        
        # Create HTTP client
        async with httpx.AsyncClient() as client:
            # Forward the request with the same method
            response = await client.request(
                request.method,
                url,
                headers=headers,
                params=request.query_params,
                content=body if body else None
            )
            
            # Return the response as-is
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
    except httpx.HTTPStatusError as e:
        logger.error(f"Proxy failed for {path}: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text) from e
    except httpx.RequestError as e:
        logger.error(f"Proxy connection error for {path}: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Could not connect to target server: {str(e)}") from e
    except Exception as e:
        logger.error(f"Proxy failed for {path}: {e}")
        raise HTTPException(status_code=500, detail=f"Proxy failed: {str(e)}") from e
