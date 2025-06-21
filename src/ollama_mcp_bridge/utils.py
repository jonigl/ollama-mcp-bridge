"""Utility functions for ollama-mcp-bridge"""
import os
import json
import re
import httpx
from typer import BadParameter
from loguru import logger


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

def validate_cli_inputs(config: str, host: str, port: int, ollama_url: str):
    """Validate CLI inputs for config file, host, port, and ollama_url."""
    # Validate config file exists
    if not os.path.isfile(config):
        raise BadParameter(f"Config file not found: {config}")

    # Validate port
    if not (1 <= port <= 65535):
        raise BadParameter(f"Port must be between 1 and 65535, got {port}")

    # Validate host (basic check)
    if not isinstance(host, str) or not host:
        raise BadParameter("Host must be a non-empty string")

    # Validate URL (basic check)
    url_pattern = re.compile(r"^https?://[\w\.-]+(:\d+)?")
    if not url_pattern.match(ollama_url):
        raise BadParameter(f"Invalid Ollama URL: {ollama_url}")
