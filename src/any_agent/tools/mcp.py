"""Tools for managing MCP (Model Context Protocol) connections and resources."""

import os
from textwrap import dedent
from abc import ABC, abstractmethod

from any_agent.config import MCPTool
from any_agent.logging import logger

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    mcp_available = True
except ImportError:
    mcp_available = False


# Global registry to keep MCP manager instances alive
_mcps = {}


class MCPServerBase(ABC):
    """Base class for MCP tools managers across different frameworks."""

    def __init__(self, mcp_tool: MCPTool):
        if not mcp_available:
            raise ImportError(
                "You need to `pip install 'any-agent[mcp]'` to use MCP tools."
            )

        # Store the original tool configuration
        self.mcp_tool = mcp_tool

        # Initialize tools list (to be populated by subclasses)
        self.tools = []

    @abstractmethod
    async def setup_tools(self):
        """Set up tools. To be implemented by subclasses."""
        pass


class SmolagentsMCPServerStdio(MCPServerBase):
    """Implementation of MCP tools manager for smolagents."""

    def __init__(self, mcp_tool: MCPTool):
        super().__init__(mcp_tool)
        # Generate a unique identifier for this manager instance
        self.id = id(self)
        self.context = None
        self.tool_collection = None

        # Register self in the global registry to prevent garbage collection
        _mcps[self.id] = self

    async def setup_tools(self):
        from smolagents import ToolCollection

        self.server_parameters = StdioServerParameters(
            command=self.mcp_tool.command,
            args=self.mcp_tool.args,
            env={**os.environ},
        )

        # Store the context manager itself
        self.context = ToolCollection.from_mcp(
            self.server_parameters, trust_remote_code=True
        )
        # Enter the context
        self.tool_collection = self.context.__enter__()
        tools = self.tool_collection.tools

        # Only add the tools listed in mcp_tool['tools'] if specified
        requested_tools = self.mcp_tool.tools
        if requested_tools:
            filtered_tools = [tool for tool in tools if tool.name in requested_tools]
            if len(filtered_tools) != len(requested_tools):
                tool_names = [tool.name for tool in filtered_tools]
                raise ValueError(
                    dedent(f"""Could not find all requested tools in the MCP server:
                                Requested: {requested_tools}
                                Set:   {tool_names}""")
                )
            self.tools = filtered_tools
        else:
            logger.info(
                "No specific tools requested for MCP server, using all available tools:"
            )
            logger.info(f"Tools available: {tools}")
            self.tools = tools

    def __del__(self):
        # Exit the context when cleanup is called
        if hasattr(self, "context") and self.context:
            try:
                self.context.__exit__(None, None, None)
                self.context = None
            except Exception as e:
                logger.error(f"Error closing MCP context: {e}")
        # Remove from registry when deleted (Smolagents-specific)
        if hasattr(self, "id") and self.id in _mcps:
            del _mcps[self.id]


class OpenAIMCPServerStdio(MCPServerBase):
    """Implementation of MCP tools manager for OpenAI agents."""

    def __init__(self, mcp_tool: MCPTool):
        super().__init__(mcp_tool)
        self.server = None
        self.loop = None

    async def setup_tools(self):
        """Set up the OpenAI MCP server with the provided configuration."""
        from agents.mcp import MCPServerStdio as OpenAIInternalMCPServerStdio

        self.server = OpenAIInternalMCPServerStdio(
            name="OpenAI MCP Server",
            params={
                "command": self.mcp_tool.command,
                "args": self.mcp_tool.args,
            },
        )

        await self.server.__aenter__()
        # Get tools from the server
        self.tools = await self.server.list_tools()
        logger.warning(
            "OpenAI MCP currently does not support filtering MCP available tools"
        )


class LangchainMCPServerStdio(MCPServerBase):
    """Implementation of MCP tools manager for LangChain agents."""

    def __init__(self, mcp_tool: MCPTool):
        super().__init__(mcp_tool)
        self.client = None
        self.session = None
        self.tools = []
        self.id = id(self)
        _mcps[self.id] = self

    async def setup_tools(self):
        """Set up the LangChain MCP server with the provided configuration."""
        from langchain_mcp_adapters.tools import load_mcp_tools

        server_params = StdioServerParameters(
            command=self.mcp_tool.command,
            args=self.mcp_tool.args,
            env={**os.environ},
        )
        self.client = stdio_client(server_params)
        self.read, self.write = await self.client.__aenter__()
        self.session = ClientSession(self.read, self.write)
        await self.session.__aenter__()
        await self.session.initialize()
        self.tools = await load_mcp_tools(self.session)

    def __del__(self):
        if hasattr(self, "id") and self.id in _mcps:
            del _mcps[self.id]


class GoogleMCPServerStdio(MCPServerBase):
    """Implementation of MCP tools manager for Google agents."""

    def __init__(self, mcp_tool: MCPTool):
        super().__init__(mcp_tool)
        self.server = None
        self.id = id(self)
        _mcps[self.id] = self

    async def setup_tools(self):
        """Set up the Google MCP server with the provided configuration."""
        from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset as GoogleMCPToolset
        from google.adk.tools.mcp_tool.mcp_toolset import (
            StdioServerParameters as GoogleStdioServerParameters,
        )

        params = GoogleStdioServerParameters(
            command=self.mcp_tool.command,
            args=self.mcp_tool.args,
            env={**os.environ},
        )

        toolset = GoogleMCPToolset(connection_params=params)
        await toolset.__aenter__()
        tools = await toolset.load_tools()
        self.tools = tools
        self.server = toolset

    def __del__(self):
        if hasattr(self, "id") and self.id in _mcps:
            del _mcps[self.id]
