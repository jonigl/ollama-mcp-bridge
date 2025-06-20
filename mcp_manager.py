"""MCP Server Management"""
import json
from typing import List, Dict
import httpx
from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack


class MCPManager:
    """Manager for MCP servers, handling tool definitions and session management."""

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.sessions: Dict[str, ClientSession] = {}
        self.all_tools: List[dict] = []
        self.exit_stack = AsyncExitStack()
        self.ollama_url = ollama_url
        self.http_client = httpx.AsyncClient()

    async def load_servers(self, config_path: str):
        """Load and connect to all MCP servers from config"""
        with open(config_path, encoding='utf-8') as f:
            config = json.load(f)
        for name, server_config in config['mcpServers'].items():
            try:
                await self._connect_server(name, server_config)
            except Exception as e:
                logger.error(f"Failed to connect to {name}: {e}")

    async def _connect_server(self, name: str, config: dict):
        """Connect to a single MCP server"""
        params = StdioServerParameters(
            command=config['command'],
            args=config['args'],
            env=config.get('env')
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(params))
        stdio, write = stdio_transport
        session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
        await session.initialize()
        self.sessions[name] = session
        meta = await session.list_tools()
        for tool in meta.tools:
            tool_def = {
                "type": "function",
                "function": {
                    "name": f"{name}_{tool.name}",
                    "description": tool.description,
                    "parameters": tool.inputSchema
                },
                "server": name,
                "original_name": tool.name
            }
            self.all_tools.append(tool_def)
        logger.info(f"Connected to '{name}' with {len(meta.tools)} tools")

    async def call_tool(self, tool_name: str, arguments: dict):
        """Call a specific tool by name with provided arguments."""
        tool_info = next((t for t in self.all_tools if t["function"]["name"] == tool_name), None)
        if not tool_info:
            raise ValueError(f"Tool {tool_name} not found")
        server_name = tool_info["server"]
        original_name = tool_info["original_name"]
        session = self.sessions[server_name]
        result = await session.call_tool(original_name, arguments)
        return result.content[0].text

    def proxy_with_tools(self, endpoint: str, payload: dict, stream: bool = False):
        """Dispatch to streaming or non-streaming logic."""
        if stream:
            # Return the async generator directly
            return self._proxy_with_tools_streaming(endpoint, payload)
        else:
            # Return the coroutine for non-streaming
            return self._proxy_with_tools_non_streaming(endpoint, payload)

    async def _proxy_with_tools_non_streaming(self, endpoint: str, payload: dict):
        payload = dict(payload)
        payload["tools"] = self.all_tools if self.all_tools else None
        # First call to Ollama
        resp = await self.http_client.post(f"{self.ollama_url}{endpoint}", json=payload)
        # Ensure we got a valid response
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
            final_resp = await self.http_client.post(f"{self.ollama_url}{endpoint}", json=followup_payload)
            final_resp.raise_for_status()
            return final_resp.json()
        return result

    async def _proxy_with_tools_streaming(self, endpoint: str, payload: dict):
        """Handle streaming requests with tool calls."""
        from utils import iter_ndjson_chunks
        payload = dict(payload)
        payload["tools"] = self.all_tools if self.all_tools else None

        async def stream_ollama(payload_to_send):
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", f"{self.ollama_url}{endpoint}", json=payload_to_send) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk

        # First streaming request
        tool_call_detected = False
        buffer_chunks = []
        ndjson_iter = iter_ndjson_chunks(stream_ollama(payload))
        async for json_obj in ndjson_iter:
            buffer_chunks.append(json.dumps(json_obj).encode() + b"\n")
            yield json.dumps(json_obj).encode() + b"\n"
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

    def _extract_tool_calls(self, result):
        return result.get("message", {}).get("tool_calls", [])

    async def _handle_tool_calls(self, messages, tool_calls):
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            arguments = tool_call["function"]["arguments"]
            tool_result = await self.call_tool(tool_name, arguments)
            logger.debug(f"Tool {tool_name} called with args {arguments}, result: {tool_result}")
            messages.append({
                "role": "tool",
                "name": tool_name,
                "content": tool_result
            })
        return messages

    async def cleanup(self):
        """Cleanup all sessions and close HTTP client."""
        await self.http_client.aclose()
        await self.exit_stack.aclose()
