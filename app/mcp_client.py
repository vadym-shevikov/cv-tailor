§"""Skeleton MCP client for interacting with a filesystem MCP server."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class MCPConfig:
    """Simple configuration options for the MCP client."""

    server_uri: str = "filesystem://kb"
    api_key: Optional[str] = None


class MCPClient:
    """Very small facade for the filesystem MCP server.

    The full implementation will establish a connection to a running MCP
    server, list available resources (the Markdown knowledge base), and allow
    agents to fetch their contents as needed. The MVP only defines the public
    methods so other modules understand how they will be called later on.
    """

    def __init__(self, config: MCPConfig | None = None):
        self.config = config or MCPConfig()
        self._is_connected = False

    def connect(self) -> None:
        """Connect to the MCP server.

        TODO: use an actual MCP client implementation once the dependency is
        available. For now we simply flip a flag so calling code can proceed.
        """

        self._is_connected = True

    def fetch_resource(self, path: str) -> str:
        """Retrieve the content of a knowledge file exposed via MCP."""

        if not self._is_connected:
            raise RuntimeError("MCP client is not connected.")

        # TODO: replace with a real MCP query.
        return f"MCP resource '{path}' is not available in the MVP yet."
