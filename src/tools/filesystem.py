"""File system tool — read, write, list, search files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config import config


class FileSystemTool:
    name = "filesystem"
    description = "Read, write, list, or search files and directories."
    input_schema = '{"action": "read|write|list|search", "path": "/absolute/path", "content": "for write", "pattern": "for search"}'

    def _check_allowed(self, path: str) -> bool:
        """Check if path is within allowed directories."""
        resolved = str(Path(path).expanduser().resolve())
        return any(
            resolved.startswith(d) for d in config.agent.allowed_directories
        )

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "list")
        path = kwargs.get("path", "~")
        path = str(Path(path).expanduser())

        if not self._check_allowed(path):
            return f"Error: Access denied. Path '{path}' is outside allowed directories."

        if action == "list":
            return self._list_dir(path)
        elif action == "read":
            return self._read_file(path)
        elif action == "write":
            content = kwargs.get("content", "")
            return self._write_file(path, content)
        elif action == "search":
            pattern = kwargs.get("pattern", "")
            return self._search(path, pattern)
        else:
            return f"Unknown action: {action}. Use: read, write, list, search"

    def _list_dir(self, path: str) -> str:
        p = Path(path)
        if not p.exists():
            return f"Error: Path '{path}' does not exist."
        if p.is_file():
            stat = p.stat()
            return f"File: {p.name} ({stat.st_size} bytes, modified {stat.st_mtime})"

        entries: list[str] = []
        try:
            for item in sorted(p.iterdir()):
                prefix = "d" if item.is_dir() else "f"
                size = item.stat().st_size if item.is_file() else 0
                entries.append(f"[{prefix}] {item.name} ({size}B)")
        except PermissionError:
            return f"Error: Permission denied for '{path}'."

        if not entries:
            return f"Directory '{path}' is empty."
        return f"Contents of {path}:\n" + "\n".join(entries[:100])

    def _read_file(self, path: str) -> str:
        p = Path(path)
        if not p.exists():
            return f"Error: File '{path}' does not exist."
        if not p.is_file():
            return f"Error: '{path}' is not a file."
        try:
            content = p.read_text(errors="replace")
            if len(content) > 8000:
                content = content[:8000] + "\n...[file truncated at 8000 chars]"
            return content
        except PermissionError:
            return f"Error: Permission denied reading '{path}'."

    def _write_file(self, path: str, content: str) -> str:
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"Successfully wrote {len(content)} chars to {path}"
        except PermissionError:
            return f"Error: Permission denied writing to '{path}'."

    def _search(self, path: str, pattern: str) -> str:
        if not pattern:
            return "Error: No search pattern provided."
        p = Path(path)
        if not p.exists():
            return f"Error: Path '{path}' does not exist."

        results: list[str] = []
        try:
            for item in p.rglob(f"*{pattern}*"):
                results.append(str(item))
                if len(results) >= 50:
                    results.append("...[limited to 50 results]")
                    break
        except PermissionError:
            pass

        if not results:
            return f"No files matching '*{pattern}*' found in {path}"
        return "\n".join(results)
