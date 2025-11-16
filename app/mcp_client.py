"""Filesystem MCP client helper.

The production architecture expects a filesystem MCP server that exposes the
`kb/` directory. To keep this repo lightweight, we mimic that setup by reading
the Markdown files directly from disk using an async-friendly interface. When
the official MCP → LangChain adapters are available, this module can swap in a
real transport without changing the public API used by the agents.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse


KBTopic = Literal["ats_tips", "cv_best_practices", "bullet_examples"]


@dataclass
class MCPConfig:
    """Configuration for the filesystem-backed MCP client."""

    server_uri: str = os.getenv("MCP_SERVER_URI", "filesystem://kb")


class FilesystemMCPClient:
    """Simple async client that reads KB files like an MCP filesystem server."""

    def __init__(self, config: MCPConfig | None = None):
        self.config = config or MCPConfig()
        self.base_path = self._resolve_base_path(self.config.server_uri)

    async def get_kb_text(self, topic: KBTopic) -> str:
        """Return the raw Markdown for the requested KB topic."""

        filename = _TOPIC_TO_FILENAME[topic]
        target = self.base_path / filename

        if not target.exists():
            return ""

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, target.read_text, "utf-8")
        except FileNotFoundError:
            return ""

    @staticmethod
    def _resolve_base_path(uri: str) -> Path:
        parsed = urlparse(uri)
        if parsed.scheme and parsed.scheme != "filesystem":
            raise ValueError("Only filesystem:// URIs are supported for MCP knowledge access")

        path_str = parsed.path or parsed.netloc or "kb"
        base_path = Path(path_str)
        if not base_path.is_absolute():
            project_root = Path(__file__).resolve().parent.parent
            base_path = project_root / base_path
        return base_path


_TOPIC_TO_FILENAME = {
    "ats_tips": "ats_tips.md",
    "cv_best_practices": "cv_best_practices.md",
    "bullet_examples": "bullet_examples.md",
}


@lru_cache(maxsize=1)
def _get_client() -> FilesystemMCPClient:
    return FilesystemMCPClient()


async def get_kb_text(topic: KBTopic) -> str:
    """Fetches the text of a KB document via the filesystem MCP client."""

    return await _get_client().get_kb_text(topic)
