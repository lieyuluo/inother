"""MCP demo integration module.

This module provides a demo MCP (Model Context Protocol) integration
for the Enterprise AI Agent platform. It is NOT a production-grade
MCP implementation, but provides a compatible interface that can be
replaced with a standard MCP SDK in the future.

Key components:
- DemoMCPServer: In-process demo MCP server with 3 demo tools
- MCPClient: Client for communicating with MCP servers
- MCPToolAdapter: Adapter to register MCP tools in the Tool Registry
"""

from app.mcp.client import MCPClient
from app.mcp.demo_server import DemoMCPServer
from app.mcp.manager import MCPManager
from app.mcp.schemas import MCPToolCallRequest, MCPToolCallResult, MCPToolDefinition

__all__ = [
    "DemoMCPServer",
    "MCPClient",
    "MCPManager",
    "MCPToolCallRequest",
    "MCPToolCallResult",
    "MCPToolDefinition",
]
