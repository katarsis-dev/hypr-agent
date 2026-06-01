"""Tool registry — auto-discovers Python tools and YAML skills."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
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
    """Register a tool instance into the registry."""
    tool_registry[tool.name] = tool
    return tool


def _is_tool_class(obj: Any) -> bool:
    """Check if an object is a valid tool class (has name, description, input_schema, execute)."""
    return (
        inspect.isclass(obj)
        and hasattr(obj, "name")
        and hasattr(obj, "description")
        and hasattr(obj, "input_schema")
        and hasattr(obj, "execute")
        and obj.__module__ != __name__
    )


def _auto_discover_python_tools() -> None:
    """Auto-discover all Python tool classes in src/tools/*.py files."""
    tools_dir = Path(__file__).parent
    for filepath in sorted(tools_dir.glob("*.py")):
        if filepath.name.startswith("_"):
            continue

        module_name = f"src.tools.{filepath.stem}"
        try:
            module = importlib.import_module(module_name)
            for _attr_name, obj in inspect.getmembers(module):
                if _is_tool_class(obj):
                    instance = obj()
                    if instance.name not in tool_registry:
                        register_tool(instance)
        except Exception as e:
            print(f"[hypr-agent] Warning: Failed to load tool from {filepath.name}: {e}")


def _load_yaml_skills() -> None:
    """Load YAML-defined skills from the skills/ directory."""
    from src.tools.yaml_skill import load_yaml_skills_from_dir

    skills_dir = Path(__file__).parent.parent.parent / "skills"
    if skills_dir.exists():
        for tool in load_yaml_skills_from_dir(skills_dir):
            if tool.name not in tool_registry:
                register_tool(tool)


# Auto-discover on import
_auto_discover_python_tools()
_load_yaml_skills()
