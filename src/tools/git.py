"""Git tool — status, log, diff, commit, branch operations."""

from __future__ import annotations

import asyncio
from typing import Any


class GitTool:
    name = "git"
    description = "Run git operations: status, log, diff, commit, branch, add. Works on any git repo."
    input_schema = '{"action": "status|log|diff|commit|branch|add", "path": "/repo/path", "message": "for commit", "args": "extra args"}'

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "status")
        path = kwargs.get("path", ".")
        message = kwargs.get("message", "")
        args = kwargs.get("args", "")

        cmd_map = {
            "status": f"git -C {path} status --short",
            "log": f"git -C {path} log --oneline -20 {args}",
            "diff": f"git -C {path} diff {args}",
            "branch": f"git -C {path} branch -a {args}",
            "add": f"git -C {path} add {args or '.'}",
        }

        if action == "commit":
            if not message:
                return "Error: commit requires a 'message' parameter."
            cmd = f'git -C {path} commit -m "{message}"'
        elif action in cmd_map:
            cmd = cmd_map[action]
        else:
            return f"Unknown git action: {action}. Use: status, log, diff, commit, branch, add"

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15.0)

            output = ""
            if stdout:
                output += stdout.decode(errors="replace")
            if stderr:
                output += stderr.decode(errors="replace")
            return output.strip() or "(no output)"
        except asyncio.TimeoutError:
            return "Error: git command timed out."
        except Exception as e:
            return f"Error: {str(e)}"
