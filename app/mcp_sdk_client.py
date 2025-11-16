"""MCP client using official SDK for filesystem access."""
from __future__ import annotations

import asyncio
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Literal, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .logging_utils import DEBUG_ENABLED, format_with_request, get_logger, truthy

logger = get_logger("mcp")

# Module-level constants
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
_MCP_AVAILABLE = True
_MCP_DISABLED_REASON = ""

# KB topic type and mapping
KBTopic = Literal["ats_tips", "bullet_examples", "cv_best_practices"]
_TOPIC_TO_FILENAME: Dict[KBTopic, str] = {
    "ats_tips": "ats_tips.md",
    "bullet_examples": "bullet_examples.md",
    "cv_best_practices": "cv_best_practices.md",
}


def _disable_mcp(reason: str) -> None:
    """Flip the global MCP flag off and log once."""
    global _MCP_AVAILABLE, _MCP_DISABLED_REASON
    if not _MCP_AVAILABLE:
        return
    _MCP_AVAILABLE = False
    _MCP_DISABLED_REASON = reason
    logger.warning(
        format_with_request("MCP disabled: %s. Using disk fallback."),
        reason,
    )


class FilesystemMCPClient:
    """Async helper that fetches KB files via MCP SDK or disk fallback."""

    def __init__(self):
        self.enabled = truthy(os.getenv("MCP_ENABLED", "true"))
        self.kb_root = (_PROJECT_ROOT / "kb").resolve()
        
        # Get command from env or use default
        cmd_str = os.getenv("MCP_COMMAND")
        if cmd_str:
            import shlex
            parts = shlex.split(cmd_str)
            self.command = parts[0]
            self.args = parts[1:]
        else:
            self.command = "mcp-server-filesystem"
            self.args = [str(self.kb_root)]
        
        self._session: Optional[ClientSession] = None
        self._session_lock = asyncio.Lock()
        self._context_stack = []
        
        if not self.enabled:
            _disable_mcp("MCP_ENABLED=false")
    
    async def _ensure_session(self) -> ClientSession:
        """Ensure we have an active MCP session."""
        async with self._session_lock:
            if self._session is None:
                if DEBUG_ENABLED:
                    logger.debug(format_with_request("Creating new MCP session"))
                
                try:
                    server_params = StdioServerParameters(
                        command=self.command,
                        args=self.args,
                    )
                    
                    # Enter the stdio_client context
                    stdio_ctx = stdio_client(server_params)
                    read, write = await stdio_ctx.__aenter__()
                    self._context_stack.append(stdio_ctx)
                    
                    # Enter the ClientSession context
                    session_ctx = ClientSession(read, write)
                    session = await session_ctx.__aenter__()
                    self._context_stack.append(session_ctx)
                    
                    # Initialize the session
                    await session.initialize()
                    
                    self._session = session
                    
                    if DEBUG_ENABLED:
                        logger.debug(format_with_request("MCP session established"))
                except Exception as e:
                    # Clean up contexts if initialization failed
                    for ctx in reversed(self._context_stack):
                        try:
                            await ctx.__aexit__(None, None, None)
                        except Exception:
                            pass
                    self._context_stack.clear()
                    raise Exception(f"Failed to initialize MCP: {e}") from e
            
            return self._session
    
    async def get_kb_text(self, topic: KBTopic) -> str:
        """Return the raw Markdown for the requested KB topic."""
        filename = _TOPIC_TO_FILENAME[topic]
        target = (self.kb_root / filename).resolve()

        if not target.exists():
            logger.warning(format_with_request("KB topic %s missing at %s"), topic, target)
            return ""

        if self.enabled and _MCP_AVAILABLE:
            try:
                contents = await self._read_via_mcp(target)
                if DEBUG_ENABLED:
                    logger.debug(format_with_request("MCP: fetched %s via MCP"), topic)
                return contents
            except Exception as exc:
                logger.exception(format_with_request("MCP error reading %s"), topic)
                _disable_mcp(f"{topic}: {exc}")

        if self.enabled and not _MCP_AVAILABLE and DEBUG_ENABLED:
            logger.debug(format_with_request("MCP disabled (%s); using disk"), _MCP_DISABLED_REASON)
        return await self._read_from_disk(target)

    async def _read_via_mcp(self, path: Path) -> str:
        """Read file via MCP SDK using the read_file tool."""
        session = await self._ensure_session()
        
        # Use the call_tool method to invoke read_file tool
        # Filesystem MCP server provides tools, not resources
        result = await session.call_tool(
            "read_file",
            arguments={"path": str(path)}
        )
        
        # Extract text content from result
        if hasattr(result, 'content'):
            text_parts = []
            for content_item in result.content:
                if hasattr(content_item, 'text'):
                    text_parts.append(content_item.text)
            if text_parts:
                return "".join(text_parts)
        
        raise Exception("No text content returned from MCP")

    async def _read_from_disk(self, path: Path) -> str:
        """Read file directly from disk."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, path.read_text, "utf-8")
    
    async def close(self) -> None:
        """Close the MCP session if open."""
        if self._session:
            # Exit all contexts in reverse order
            for ctx in reversed(self._context_stack):
                try:
                    await ctx.__aexit__(None, None, None)
                except Exception:
                    pass
            self._context_stack.clear()
            self._session = None


@lru_cache(maxsize=1)
def _get_client() -> FilesystemMCPClient:
    return FilesystemMCPClient()


async def get_kb_text(topic: KBTopic) -> str:
    """Fetch the text of a KB document via MCP (or disk fallback)."""
    return await _get_client().get_kb_text(topic)

