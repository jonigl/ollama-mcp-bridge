"""MCP Server Management"""
import json
from typing import List, Dict
from contextlib import AsyncExitStack
import os
import httpx
from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPManager:
    """Manager for MCP servers, handling tool definitions and session management."""

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        """Initialize MCP Manager

        Args:
            ollama_url: URL of the Ollama server
        """
        self.sessions: Dict[str, ClientSession] = {}
        self.all_tools: List[dict] = []
        self.exit_stack = AsyncExitStack()
        self.ollama_url = ollama_url
        self.http_client = httpx.AsyncClient()

    async def load_servers(self, config_path: str):
        """Load and connect to all MCP servers from config"""
        config_dir = os.path.dirname(os.path.abspath(config_path))
        with open(config_path, encoding='utf-8') as f:
            config = json.load(f)
        for name, server_config in config['mcpServers'].items():
            resolved_config = dict(server_config)
            resolved_config['cwd'] = config_dir
            await self._connect_server(name, resolved_config)

    async def _connect_server(self, name: str, config: dict):
        """Connect to a single MCP server"""
        params = StdioServerParameters(

            command=config['command'],
            args=config['args'],
            env=config.get('env'),
            cwd=config.get('cwd')
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
                    "name": f"{name}.{tool.name}",
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

    async def cleanup(self):
        """Cleanup all sessions and close HTTP client."""
        await self.http_client.aclose()
        await self.exit_stack.aclose()
