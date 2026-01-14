"""Service for handling proxy requests to Ollama"""

import json
from typing import Dict, Any, AsyncGenerator, Union
import httpx
from fastapi import Request, Response, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from .utils import check_ollama_health_async, iter_ndjson_chunks, get_ollama_proxy_timeout_config
from .mcp_manager import MCPManager


class ProxyService:
    """Service handling all proxy-related operations to Ollama with or without MCP tools"""

    def __init__(self, mcp_manager: MCPManager):
        """Initialize the proxy service with an MCP manager."""
        self.mcp_manager = mcp_manager
        is_set, timeout_seconds = get_ollama_proxy_timeout_config()
        # Preserve existing behavior when unset (no timeout for /api/chat). If set, honor it.
        self.http_client = httpx.AsyncClient(timeout=timeout_seconds) if is_set else httpx.AsyncClient(timeout=None)

    def _maybe_prepend_system_prompt(self, messages: list) -> list:
        """If a system prompt is configured on the MCP manager, ensure it is the first message.

        Does not duplicate if the first message already has role 'system'.
        """
        system_prompt = getattr(self.mcp_manager, "system_prompt", None)
        if not system_prompt:
            return messages

        # If messages is empty or first message isn't a system role, prepend
        if not messages or messages[0].get("role") != "system":
            return [{"role": "system", "content": system_prompt}] + messages
        return messages

    async def health_check(self) -> Dict[str, Any]:
        """Check the health of the Ollama server and MCP setup"""
        ollama_healthy = await check_ollama_health_async(self.mcp_manager.ollama_url)
        return {
            "status": "healthy" if ollama_healthy else "degraded",
            "ollama_status": "running" if ollama_healthy else "not accessible",
            "tools": len(self.mcp_manager.all_tools),
        }

    async def proxy_chat_with_tools(
        self, payload: Dict[str, Any], stream: bool = False
    ) -> Union[Dict[str, Any], StreamingResponse]:
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
                    media_type="application/json",
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

    async def _make_final_llm_call(self, endpoint: str, payload: Dict[str, Any], messages: list) -> Dict[str, Any]:
        """Make a final LLM call without tools to get final answer after tool execution"""
        final_payload = dict(payload)
        final_payload["stream"] = False  # Explicitly disable streaming to get single JSON response
        final_payload["messages"] = messages
        final_payload["tools"] = None  # Don't allow more tool calls
        resp = await self.http_client.post(f"{self.mcp_manager.ollama_url}{endpoint}", json=final_payload)
        resp.raise_for_status()
        return resp.json()

    async def _stream_final_llm_call(
        self, stream_ollama, payload: Dict[str, Any], messages: list
    ) -> AsyncGenerator[bytes, None]:
        """Stream a final LLM call without tools to get final answer after tool execution"""
        final_payload = dict(payload)
        final_payload["messages"] = messages
        final_payload["tools"] = None  # Don't allow more tool calls

        ndjson_iter = iter_ndjson_chunks(stream_ollama(final_payload))
        async for json_obj in ndjson_iter:
            buffer_chunk = json.dumps(json_obj).encode() + b"\n"
            yield buffer_chunk

    async def _proxy_with_tools_non_streaming(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle non-streaming chat requests with tools"""
        payload = dict(payload)
        payload["stream"] = False  # Explicitly disable streaming to get single JSON response
        payload["tools"] = self.mcp_manager.all_tools if self.mcp_manager.all_tools else None
        messages = payload.get("messages") or []
        messages = self._maybe_prepend_system_prompt(messages)

        # Get max tool rounds from app state (None means unlimited)
        max_rounds = getattr(self.mcp_manager, "max_tool_rounds", None)
        current_round = 0

        # Loop to handle potentially multiple rounds of tool calls
        while True:
            # Call Ollama
            current_payload = dict(payload)
            current_payload["messages"] = messages
            resp = await self.http_client.post(f"{self.mcp_manager.ollama_url}{endpoint}", json=current_payload)
            resp.raise_for_status()
            result = resp.json()

            # Check for tool calls
            tool_calls = self._extract_tool_calls(result)
            if not tool_calls:
                # No more tool calls, return final result
                return result

            # Add assistant's response with tool calls
            response_content = result.get("message", {}).get("content", "")
            messages.append({"role": "assistant", "content": response_content, "tool_calls": tool_calls})

            # Execute tool calls and add results to messages
            messages = await self._handle_tool_calls(messages, tool_calls)

            # Check if we've reached the maximum number of rounds
            current_round += 1
            if max_rounds is not None and current_round >= max_rounds:
                logger.warning(
                    f"Reached maximum tool execution rounds ({max_rounds}), making final LLM call with tool results"
                )
                return await self._make_final_llm_call(endpoint, payload, messages)

            # Continue loop to get next response

    async def _proxy_with_tools_streaming(self, endpoint: str, payload: Dict[str, Any]) -> AsyncGenerator[bytes, None]:
        """Handle streaming chat requests with tools"""

        payload = dict(payload)
        payload["tools"] = self.mcp_manager.all_tools if self.mcp_manager.all_tools else None
        messages = list(payload.get("messages") or [])
        messages = self._maybe_prepend_system_prompt(messages)

        async def stream_ollama(payload_to_send):
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST", f"{self.mcp_manager.ollama_url}{endpoint}", json=payload_to_send
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk

        # Get max tool rounds from app state (None means unlimited)
        max_rounds = getattr(self.mcp_manager, "max_tool_rounds", None)
        current_round = 0

        # Loop to handle potentially multiple rounds of tool calls
        while True:
            current_payload = dict(payload)
            current_payload["messages"] = messages

            tool_calls = []
            response_text = ""

            ndjson_iter = iter_ndjson_chunks(stream_ollama(current_payload))
            async for json_obj in ndjson_iter:
                # Stream all chunks directly to the client
                buffer_chunk = json.dumps(json_obj).encode() + b"\n"
                yield buffer_chunk

                extracted_calls = self._extract_tool_calls(json_obj)
                if extracted_calls:
                    tool_calls = extracted_calls

                if json_obj.get("done"):
                    response_text = json_obj.get("message", {}).get("content", "")
                    if extracted_calls:
                        tool_calls = extracted_calls
                    break

            if not tool_calls:
                # No tool calls required, streaming complete
                break

            # Tool calls detected; execute them
            messages.append({"role": "assistant", "content": response_text, "tool_calls": tool_calls})
            messages = await self._handle_tool_calls(messages, tool_calls)

            # Check if we've reached the maximum number of rounds
            current_round += 1
            if max_rounds is not None and current_round >= max_rounds:
                logger.warning(
                    f"Reached maximum tool execution rounds ({max_rounds}), making final LLM call with tool results"
                )
                # Stream the final LLM response with tool results (no more tools allowed)
                async for chunk in self._stream_final_llm_call(stream_ollama, payload, messages):
                    yield chunk
                break

    def _extract_tool_calls(self, result: Dict[str, Any]) -> list:
        """Extract tool calls from response"""
        tool_calls = result.get("message", {}).get("tool_calls", [])
        if tool_calls:
            logger.debug(f"Extracted tool_calls from response: {tool_calls}")
        return tool_calls

    async def _handle_tool_calls(self, messages: list, tool_calls: list) -> list:
        """Process tool calls and get results"""
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            arguments = tool_call["function"]["arguments"]
            tool_result = await self.mcp_manager.call_tool(tool_name, arguments)
            logger.debug(f"Tool {tool_name} called with args {arguments}, result: {tool_result}")
            messages.append({"role": "tool", "tool_name": tool_name, "content": tool_result})
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
            is_set, timeout_seconds = get_ollama_proxy_timeout_config()
            client_kwargs = {"timeout": timeout_seconds} if is_set else {}
            async with httpx.AsyncClient(**client_kwargs) as client:
                # Forward the request with the same method
                response = await client.request(
                    request.method, url, headers=headers, params=request.query_params, content=body if body else None
                )

                # Return the response as-is
                return Response(
                    content=response.content, status_code=response.status_code, headers=dict(response.headers)
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
