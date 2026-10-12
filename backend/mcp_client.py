"""The single connection every agent tool goes through to reach the
campus-customs MCP server. Nothing in backend/ opens the database directly -
every shop fact and every write comes from an MCP tool call made here.

Uses the `mcp` v1 client API (ClientSession + stdio_client) to match the
server in mcp_server/server.py, which is built on the v1 FastMCP API and is
pinned to `mcp<2` in requirements.txt. (pydantic-ai's own built-in MCP
toolset needs mcp>=2, which would break the server - see backend/README.md.)
"""

import json
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"

_SERVER_PARAMS = StdioServerParameters(
    command=str(VENV_PYTHON),
    args=["-m", "mcp_server.server"],
    cwd=str(PROJECT_ROOT),
    env={"PYTHONPATH": str(PROJECT_ROOT)},
)


class MCPClient:
    """One lazily-started stdio connection to the campus-customs server, reused by every agent."""

    def __init__(self) -> None:
        self._session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None

    async def connect(self) -> None:
        if self._session is not None:
            return
        self._stack = AsyncExitStack()
        read, write = await self._stack.enter_async_context(stdio_client(_SERVER_PARAMS))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._session = None
        self._stack = None

    async def call(self, tool_name: str, **arguments) -> dict:
        if self._session is None:
            await self.connect()
        assert self._session is not None
        result = await self._session.call_tool(tool_name, arguments)
        if result.isError:
            detail = result.content[0].text if result.content else "unknown MCP error"
            raise RuntimeError(f"MCP tool {tool_name!r} failed: {detail}")
        return json.loads(result.content[0].text)


mcp_client = MCPClient()
