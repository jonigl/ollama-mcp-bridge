"""Service for handling proxy requests to Ollama"""
import json
from typing import Dict, Any, AsyncGenerator, Union
import httpx
from fastapi import Request, Response, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from .utils import check_ollama_health_async, iter_ndjson_chunks
from .mcp_manager import MCPManager


class ProxyService:
    """Service handling all proxy-related operations to Ollama with or without MCP tools"""

    def __init__(self, mcp_manager: MCPManager):
        """Initialize the proxy service with an MCP manager."""
        self.mcp_manager = mcp_manager
        self.http_client = httpx.AsyncClient(timeout=None)

    async def health_check(self) -> Dict[str, Any]:
        """Check the health of the Ollama server and MCP setup"""
        ollama_healthy = await check_ollama_health_async(self.mcp_manager.ollama_url)
        return {
            "status": "healthy" if ollama_healthy else "degraded",
            "ollama_status": "running" if ollama_healthy else "not accessible",
            "tools": len(self.mcp_manager.all_tools)
        }

    async def proxy_chat_with_tools(self, payload: Dict[str, Any], stream: bool = False) -> Union[Dict[str, Any], StreamingResponse]:
        """Handle chat requests with potential tool integration

        Args:
            payload: The request payload
            stream: Whether to use streaming response

        Returns:
            Either a dictionary response or a StreamingResponse
        """
        if not await check_ollama_health_async(self.mcp_manager.ollama_url):
            raise httpx.RequestError("Ollama server not accessible", request=None)

        try:
            if stream:
                return StreamingResponse(
                    self._proxy_with_tools_streaming(endpoint="/api/chat", payload=payload),
                    media_type="application/json"
                )
            else:
                return await self._proxy_with_tools_non_streaming(endpoint="/api/chat", payload=payload)
        except httpx.HTTPStatusError as e:
            logger.error(f"Chat proxy failed: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Chat connection error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Chat proxy failed: {e}")
            raise

    async def _proxy_with_tools_non_streaming(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle non-streaming chat requests with tools"""
        payload = dict(payload)
        payload["tools"] = self.mcp_manager.all_tools if self.mcp_manager.all_tools else None

        # First call to Ollama
        resp = await self.http_client.post(f"{self.mcp_manager.ollama_url}{endpoint}", json=payload)
        resp.raise_for_status()
        result = resp.json()

        # Check for tool calls
        tool_calls = self._extract_tool_calls(result)
        if tool_calls:
            messages = payload.get("messages") or []
            messages = await self._handle_tool_calls(messages, tool_calls)
            followup_payload = dict(payload)
            followup_payload["messages"] = messages
            followup_payload.pop("tools", None)
            final_resp = await self.http_client.post(
                f"{self.mcp_manager.ollama_url}{endpoint}",
                json=followup_payload
            )
            final_resp.raise_for_status()
            return final_resp.json()
        return result

    async def _proxy_with_tools_streaming(self, endpoint: str, payload: Dict[str, Any]) -> AsyncGenerator[bytes, None]:
        """Handle streaming chat requests with tools"""
        payload = dict(payload)
        payload["tools"] = self.mcp_manager.all_tools if self.mcp_manager.all_tools else None

        async def stream_ollama(payload_to_send):
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", f"{self.mcp_manager.ollama_url}{endpoint}", json=payload_to_send) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk

        # First streaming request
        tool_call_detected = False
        ndjson_iter = iter_ndjson_chunks(stream_ollama(payload))
        async for json_obj in ndjson_iter:
            buffer_chunk = json.dumps(json_obj).encode() + b"\n"
            yield buffer_chunk
            tool_calls = self._extract_tool_calls(json_obj)
            if tool_calls:
                tool_call_detected = True
                break  # Stop streaming initial response, go to tool call handling

        if tool_call_detected:
            # Handle tool calls
            messages = payload.get("messages") or []
            messages = await self._handle_tool_calls(messages, tool_calls)
            followup_payload = dict(payload)
            followup_payload["messages"] = messages
            followup_payload.pop("tools", None)
            # Stream the final response
            async for chunk in stream_ollama(followup_payload):
                yield chunk

    def _extract_tool_calls(self, result: Dict[str, Any]) -> list:
        """Extract tool calls from response"""
        return result.get("message", {}).get("tool_calls", [])

    async def _handle_tool_calls(self, messages: list, tool_calls: list) -> list:
        """Process tool calls and get results"""
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            arguments = tool_call["function"]["arguments"]
            tool_result = await self.mcp_manager.call_tool(tool_name, arguments)
            logger.debug(f"Tool {tool_name} called with args {arguments}, result: {tool_result}")
            messages.append({
                "role": "tool",
                "name": tool_name,
                "content": tool_result
            })
        return messages

    async def proxy_generic_request(self, path: str, request: Request) -> Response:
        """Proxy any request to Ollama

        Args:
            path: The path to proxy to
            request: The FastAPI request object

        Returns:
            FastAPI Response object
        """
        # Get ollama URL from MCP manager
        ollama_url = self.mcp_manager.ollama_url

        try:
            # Create URL to forward to
            url = f"{ollama_url}/{path}"

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

    async def cleanup(self):
        """Close HTTP client resources"""
        await self.http_client.aclose()
