"""MCP Server Management"""

import json
import sys
from typing import List, Dict
from contextlib import AsyncExitStack
import os
import httpx
from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from .utils import expand_dict_env_vars, get_ollama_proxy_timeout_config


class MCPManager:
    """Manager for MCP servers, handling tool definitions and session management."""

    def __init__(self, ollama_url: str = "http://localhost:11434", system_prompt: str = None):
        """Initialize MCP Manager

        Args:
            ollama_url: URL of the Ollama server
        """
        self.sessions: Dict[str, ClientSession] = {}
        self.all_tools: List[dict] = []
        self.exit_stack = AsyncExitStack()
        self.ollama_url = ollama_url
        # Optional system prompt that can be prepended to messages
        self.system_prompt = system_prompt
        is_set, timeout_seconds = get_ollama_proxy_timeout_config()
        self.http_client = httpx.AsyncClient(timeout=timeout_seconds) if is_set else httpx.AsyncClient()

    async def load_servers(self, config_path: str):
        """Load and connect to all MCP servers from config"""
        config_dir = os.path.dirname(os.path.abspath(config_path))
        try:
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse config file '{config_path}': {e}")
            raise ValueError(f"Invalid JSON in config file '{config_path}': {e}") from e
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            raise

        if "mcpServers" not in config:
            logger.error(f"Config file '{config_path}' missing 'mcpServers' key")
            raise ValueError(f"Config file '{config_path}' missing 'mcpServers' key")

        for name, server_config in config["mcpServers"].items():
            resolved_config = dict(server_config)
            resolved_config["cwd"] = config_dir
            await self._connect_server(name, resolved_config)

    async def _connect_server(self, name: str, config: dict):
        """Connect to a single MCP server"""
        server_stack = AsyncExitStack()

        async def _safe_close_stack() -> None:
            try:
                await server_stack.aclose()
            except BaseException as close_error:
                # Some transports can raise ExceptionGroup/RuntimeError while unwinding
                # after a failed connect; avoid crashing startup because of cleanup.
                logger.debug(f"Error cleaning up failed connection for '{name}': {close_error}")

        try:
            # Validate toolFilter configuration if present
            tool_filter = config.get("toolFilter", {})
            if tool_filter:
                mode = tool_filter.get("mode", "include")
                if mode not in ["include", "exclude"]:
                    logger.error(
                        f"Invalid toolFilter mode '{mode}' for server '{name}'. Must be 'include' or 'exclude'."
                    )
                    sys.exit(1)

            # Expand env vars
            cwd = config.get("cwd", os.getcwd())
            config = expand_dict_env_vars(config, cwd)

            if "command" in config:
                params = StdioServerParameters(
                    command=config["command"], args=config.get("args", []), env=config.get("env"), cwd=config.get("cwd")
                )
                transport = await server_stack.enter_async_context(stdio_client(params))
                read, write = transport
            elif "url" in config:
                url = config["url"]
                headers = config.get("headers", {})

                # Determine connection type by URL suffix or default to StreamableHTTP
                if url.rstrip("/").endswith("/sse"):
                    transport = await server_stack.enter_async_context(sse_client(url=url, headers=headers))
                    read, write = transport
                else:
                    # Default to StreamableHTTP if not explicitly /sse
                    transport = await server_stack.enter_async_context(streamablehttp_client(url=url, headers=headers))
                    # streamablehttp_client yields (read, write, get_session_id)
                    read, write, _ = transport
            else:
                raise ValueError(f"Invalid MCP server config for '{name}': must have 'command' or 'url'")

            session = await server_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.sessions[name] = session
            meta = await session.list_tools()

            # Apply tool filtering if configured
            tool_filter = config.get("toolFilter", {})
            filter_mode = tool_filter.get("mode", "include")
            filter_tools = tool_filter.get("tools", [])

            all_tool_names = [tool.name for tool in meta.tools]
            filtered_tools = []
            found_tools = []
            missing_tools = []
            excluded_tools = []

            if filter_tools:
                if filter_mode == "include":
                    # Include mode: only add tools in the filter list
                    for tool in meta.tools:
                        if tool.name in filter_tools:
                            filtered_tools.append(tool)
                            found_tools.append(tool.name)
                    # Track which filter tools were not found
                    missing_tools = [t for t in filter_tools if t not in all_tool_names]
                elif filter_mode == "exclude":
                    # Exclude mode: add all tools except those in the filter list
                    for tool in meta.tools:
                        if tool.name not in filter_tools:
                            filtered_tools.append(tool)
                        else:
                            excluded_tools.append(tool.name)
            else:
                # No filter or empty filter list: add all tools
                filtered_tools = list(meta.tools)

            # Add filtered tools to the manager
            for tool in filtered_tools:
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": f"{name}.{tool.name}",
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    },
                    "server": name,
                    "original_name": tool.name,
                }
                self.all_tools.append(tool_def)

            # Transfer ownership of the server stack to the main exit stack
            self.exit_stack.push_async_callback(server_stack.pop_all().aclose)

            # Log connection results with filtering information
            if filter_tools:
                if filter_mode == "include":
                    logger.info(
                        f"Connected to '{name}' with {len(filtered_tools)}/{len(meta.tools)} tools "
                        f"({len(meta.tools) - len(filtered_tools)} filtered)"
                    )
                    if found_tools:
                        logger.info(f"Server '{name}': enabled tools [{', '.join(found_tools)}]")
                    if missing_tools:
                        logger.warning(f"Server '{name}': tools not found in filter [{', '.join(missing_tools)}]")
                elif filter_mode == "exclude":
                    logger.info(
                        f"Connected to '{name}' with {len(filtered_tools)}/{len(meta.tools)} tools "
                        f"({len(excluded_tools)} excluded)"
                    )
                    if excluded_tools:
                        logger.info(f"Server '{name}': excluded tools [{', '.join(excluded_tools)}]")
            else:
                all_tool_names_list = [tool.name for tool in filtered_tools]
                logger.info(f"Connected to '{name}' with {len(meta.tools)} tools")
                if all_tool_names_list:
                    logger.info(f"Server '{name}': available tools [{', '.join(all_tool_names_list)}]")

        except (SystemExit, KeyboardInterrupt):
            await _safe_close_stack()
            raise

        except BaseException as e:
            # This may include CancelledError depending on runtime.
            logger.error(f"Failed to connect to MCP server '{name}': {repr(e)}")
            await _safe_close_stack()

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
