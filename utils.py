"""Utility functions for ollama-mcp-bridge"""
import httpx
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
