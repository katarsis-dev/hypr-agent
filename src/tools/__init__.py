"""Tool registry — auto-discovers and registers all available tools."""

from __future__ import annotations

from typing import Any, Protocol


class Tool(Protocol):
    """Protocol for agent tools."""

    name: str
    description: str
    input_schema: str

    async def execute(self, **kwargs: Any) -> str: ...


# Registry populated at import time
tool_registry: dict[str, Any] = {}


def register_tool(tool: Any) -> Any:
    """Decorator/function to register a tool."""
    tool_registry[tool.name] = tool
    return tool


# Import all tool modules to trigger registration
from src.tools.filesystem import FileSystemTool  # noqa: E402
from src.tools.shell import ShellTool  # noqa: E402
from src.tools.system import SystemTool  # noqa: E402
from src.tools.code import CodeTool  # noqa: E402
from src.tools.search import SearchTool  # noqa: E402

register_tool(FileSystemTool())
register_tool(ShellTool())
register_tool(SystemTool())
register_tool(CodeTool())
register_tool(SearchTool())
