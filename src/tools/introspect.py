"""Introspect tool — let the agent read its own source code and structure."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

# The agent's own project root
AGENT_ROOT = Path(__file__).parent.parent.parent

# Files the agent is NOT allowed to modify (core brain)
PROTECTED_FILES = {
    "src/agent/loop.py",
    "src/agent/prompt.py",
    "src/main.py",
    "src/api/routes.py",
    "src/api/models.py",
    "src/config.py",
    "src/llm/client.py",
}

# Directories the agent can freely edit
EDITABLE_DIRS = {
    "src/tools/",
    "skills/",
    "static/",
    "templates/",
}


class IntrospectTool:
    name = "introspect"
    description = (
        "Inspect the agent's own source code and structure. "
        "Use to understand your own codebase, read your tool implementations, "
        "check config, or list available files. Cannot modify protected core files."
    )
    input_schema = '{"action": "map|read|list_tools|config|logs", "path": "relative path within agent (e.g. src/tools/git.py)"}'

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "map")
        path = kwargs.get("path", "")

        if action == "map":
            return self._get_codebase_map()
        elif action == "read":
            return self._read_file(path)
        elif action == "list_tools":
            return self._list_tools()
        elif action == "config":
            return self._read_file("config.yaml")
        elif action == "logs":
            return await self._get_recent_logs()
        else:
            return f"Unknown action: {action}. Use: map, read, list_tools, config, logs"

    def _get_codebase_map(self) -> str:
        """Return a structural map of the agent's codebase."""
        lines = [
            "# hypr-agent codebase map",
            f"Root: {AGENT_ROOT}",
            "",
            "## Core (PROTECTED — do not modify):",
        ]
        for f in sorted(PROTECTED_FILES):
            full = AGENT_ROOT / f
            size = full.stat().st_size if full.exists() else 0
            lines.append(f"  {f} ({size} bytes)")

        lines.append("")
        lines.append("## Editable (tools, skills, config, UI):")

        for d in sorted(EDITABLE_DIRS):
            dir_path = AGENT_ROOT / d
            if dir_path.exists():
                for f in sorted(dir_path.rglob("*")):
                    if f.is_file() and not f.name.startswith("."):
                        rel = f.relative_to(AGENT_ROOT)
                        lines.append(f"  {rel} ({f.stat().st_size} bytes)")

        # Config
        cfg = AGENT_ROOT / "config.yaml"
        if cfg.exists():
            lines.append(f"  config.yaml ({cfg.stat().st_size} bytes)")

        lines.append("")
        lines.append("## Permissions:")
        lines.append("  - CAN edit: src/tools/*, skills/*, config.yaml, static/*, templates/*")
        lines.append("  - CANNOT edit: src/agent/*, src/main.py, src/api/*, src/llm/*")
        lines.append("  - CAN read: everything")

        return "\n".join(lines)

    def _read_file(self, path: str) -> str:
        """Read a file from the agent's codebase."""
        if not path:
            return "Error: No path provided. Use relative path like 'src/tools/git.py'"

        filepath = AGENT_ROOT / path
        if not filepath.exists():
            return f"Error: File not found: {path}"
        if not filepath.is_file():
            return f"Error: Not a file: {path}"

        try:
            content = filepath.read_text()
            if len(content) > 8000:
                content = content[:8000] + "\n...[truncated at 8000 chars]"
            return f"--- {path} ---\n{content}"
        except Exception as e:
            return f"Error reading {path}: {e}"

    def _list_tools(self) -> str:
        """List all tool files with descriptions."""
        tools_dir = AGENT_ROOT / "src" / "tools"
        skills_dir = AGENT_ROOT / "skills"
        lines = ["# Registered tools\n", "## Python tools (src/tools/):\n"]

        for f in sorted(tools_dir.glob("*.py")):
            if f.name.startswith("_") or f.name == "__init__.py":
                continue
            # Try to extract the description
            content = f.read_text()
            desc = ""
            for line in content.split("\n"):
                if "description" in line and "=" in line:
                    desc = line.split("=", 1)[1].strip().strip('"\'()')[:80]
                    break
            lines.append(f"  - {f.name}: {desc}")

        lines.append("\n## YAML skills (skills/):\n")
        if skills_dir.exists():
            for f in sorted(skills_dir.glob("*.yaml")):
                if f.name.startswith("_"):
                    continue
                lines.append(f"  - {f.name}")

        return "\n".join(lines)

    async def _get_recent_logs(self) -> str:
        """Get recent agent logs/errors."""
        try:
            proc = await asyncio.create_subprocess_shell(
                "journalctl --user -u hypr-agent --no-pager -n 50 2>/dev/null || tail -50 /tmp/hypr-agent.log 2>/dev/null || echo 'No logs found'",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            return stdout.decode(errors="replace") or "(no logs found)"
        except Exception:
            return "(could not retrieve logs)"
