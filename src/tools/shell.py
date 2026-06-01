"""Shell tool — execute system commands safely."""

from __future__ import annotations

import asyncio
from typing import Any

from src.config import config

# Commands that should never be run
BLOCKED_COMMANDS = {
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=/dev/zero",
    ":(){ :|:& };:",
    "> /dev/sda",
    "chmod -R 777 /",
}

# Dangerous prefixes to warn about
DANGEROUS_PREFIXES = ["rm -rf", "sudo rm", "dd ", "mkfs", "format"]


class ShellTool:
    name = "shell"
    description = "Execute a shell command and return its output. Use for system tasks, file operations, package info, etc."
    input_schema = '{"command": "the shell command to run"}'

    async def execute(self, **kwargs: Any) -> str:
        command = kwargs.get("command") or kwargs.get("input", "")
        if not command:
            return "Error: No command provided."

        if not config.agent.allow_shell:
            return "Error: Shell access is disabled in configuration."

        # Safety check
        cmd_lower = command.lower().strip()
        for blocked in BLOCKED_COMMANDS:
            if blocked in cmd_lower:
                return f"Error: Blocked dangerous command: {command}"

        for prefix in DANGEROUS_PREFIXES:
            if cmd_lower.startswith(prefix):
                return f"Warning: Potentially dangerous command detected. Refusing to execute: {command}"

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=None,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                proc.kill()
                return "Error: Command timed out after 30 seconds."

            output = ""
            if stdout:
                output += stdout.decode(errors="replace")
            if stderr:
                output += "\nSTDERR: " + stderr.decode(errors="replace")

            if proc.returncode != 0:
                output += f"\n[Exit code: {proc.returncode}]"

            return output.strip() or "(no output)"

        except Exception as e:
            return f"Error running command: {str(e)}"
