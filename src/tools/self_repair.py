"""Self-repair tool — lets the agent fix its own tools, skills, and config."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

# The agent's own project root
AGENT_ROOT = Path(__file__).parent.parent.parent

# Backup directory
BACKUP_DIR = AGENT_ROOT / ".backups"

# Files the agent is NOT allowed to modify (core brain)
PROTECTED_FILES = {
    "src/agent/loop.py",
    "src/agent/prompt.py",
    "src/agent/memory.py",
    "src/agent/profile.py",
    "src/main.py",
    "src/api/routes.py",
    "src/api/models.py",
    "src/config.py",
    "src/llm/client.py",
    "src/tools/__init__.py",
    "src/tools/self_repair.py",
    "src/tools/introspect.py",
}

# Directories the agent CAN modify
ALLOWED_PREFIXES = (
    "src/tools/",
    "skills/",
    "static/",
    "templates/",
    "config.yaml",
)


class SelfRepairTool:
    name = "self_repair"
    description = (
        "Fix bugs in your own tools, skills, config, or UI. "
        "Creates a backup before any edit. Cannot modify core agent files (loop, prompt, main). "
        "Use introspect first to read the file, then self_repair to fix it."
    )
    input_schema = '{"action": "edit|create|delete|backup_restore|restart", "path": "relative path (e.g. src/tools/git.py)", "content": "new file content (for edit/create)", "reason": "why you are making this change"}'

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        reason = kwargs.get("reason", "no reason given")

        if action == "edit":
            return self._edit_file(path, content, reason)
        elif action == "create":
            return self._create_file(path, content, reason)
        elif action == "delete":
            return self._delete_file(path, reason)
        elif action == "backup_restore":
            return self._restore_backup(path)
        elif action == "restart":
            return self._get_restart_instructions()
        else:
            return f"Unknown action: {action}. Use: edit, create, delete, backup_restore, restart"

    def _is_protected(self, path: str) -> bool:
        """Check if a file is protected from modification."""
        return path in PROTECTED_FILES

    def _is_allowed(self, path: str) -> bool:
        """Check if a file is in an allowed edit location."""
        if path == "config.yaml":
            return True
        return any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES)

    def _backup(self, filepath: Path, path: str) -> str | None:
        """Create a backup of a file before modifying it."""
        if not filepath.exists():
            return None
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = path.replace("/", "_")
        backup_path = BACKUP_DIR / f"{safe_name}.{timestamp}.bak"
        shutil.copy2(filepath, backup_path)
        return str(backup_path)

    def _edit_file(self, path: str, content: str, reason: str) -> str:
        """Edit an existing file (with safety checks and backup)."""
        if not path:
            return "Error: No path provided."
        if not content:
            return "Error: No content provided. Include the full new file content."
        if self._is_protected(path):
            return f"BLOCKED: '{path}' is a protected core file. You cannot modify it."
        if not self._is_allowed(path):
            return f"BLOCKED: '{path}' is not in an editable directory. Allowed: {', '.join(ALLOWED_PREFIXES)}"

        filepath = AGENT_ROOT / path
        if not filepath.exists():
            return f"Error: File not found: {path}. Use action='create' for new files."

        # Backup
        backup = self._backup(filepath, path)

        # Write
        try:
            filepath.write_text(content)
            result = f"Fixed: {path}\nReason: {reason}\nBackup: {backup}"
            return result
        except Exception as e:
            return f"Error writing {path}: {e}"

    def _create_file(self, path: str, content: str, reason: str) -> str:
        """Create a new file."""
        if not path:
            return "Error: No path provided."
        if not content:
            return "Error: No content provided."
        if self._is_protected(path):
            return f"BLOCKED: '{path}' is a protected path."
        if not self._is_allowed(path):
            return f"BLOCKED: '{path}' is not in an editable directory. Allowed: {', '.join(ALLOWED_PREFIXES)}"

        filepath = AGENT_ROOT / path
        if filepath.exists():
            return f"Error: File already exists: {path}. Use action='edit' to modify."

        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
            return f"Created: {path}\nReason: {reason}"
        except Exception as e:
            return f"Error creating {path}: {e}"

    def _delete_file(self, path: str, reason: str) -> str:
        """Delete a file (with backup)."""
        if not path:
            return "Error: No path provided."
        if self._is_protected(path):
            return f"BLOCKED: '{path}' is a protected core file."
        if not self._is_allowed(path):
            return f"BLOCKED: '{path}' is not in an editable directory."

        filepath = AGENT_ROOT / path
        if not filepath.exists():
            return f"Error: File not found: {path}"

        # Backup first
        backup = self._backup(filepath, path)
        filepath.unlink()
        return f"Deleted: {path}\nReason: {reason}\nBackup: {backup}"

    def _restore_backup(self, path: str) -> str:
        """Restore the most recent backup of a file."""
        if not path:
            return "Error: No path provided."

        safe_name = path.replace("/", "_")
        backups = sorted(BACKUP_DIR.glob(f"{safe_name}.*.bak")) if BACKUP_DIR.exists() else []

        if not backups:
            return f"No backups found for: {path}"

        latest = backups[-1]
        filepath = AGENT_ROOT / path
        shutil.copy2(latest, filepath)
        return f"Restored: {path} from backup {latest.name}"

    def _get_restart_instructions(self) -> str:
        """Return instructions to restart the agent."""
        return (
            "To apply changes, the agent needs to restart.\n"
            "Options:\n"
            "  1. User runs: systemctl --user restart hypr-agent\n"
            "  2. User runs: cd ~/hypr-agent && ./run.sh\n"
            "  3. User manually restarts the FastAPI process\n\n"
            "Note: Tool/skill changes are auto-discovered on restart.\n"
            "Config changes take effect on restart.\n"
            "Profile changes take effect immediately (no restart needed)."
        )
