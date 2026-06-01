"""Hyprland window manager control via hyprctl."""

from __future__ import annotations

import asyncio
from typing import Any


class HyprlandTool:
    name = "hyprland"
    description = "Control Hyprland window manager: list windows, move/resize/focus windows, switch workspaces, get active window info. Uses hyprctl."
    input_schema = '{"action": "windows|workspaces|active|focus|move|resize|workspace|dispatch", "args": "arguments for the action"}'

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "windows")
        args = kwargs.get("args", "")

        cmd_map = {
            "windows": "hyprctl clients -j",
            "workspaces": "hyprctl workspaces -j",
            "active": "hyprctl activewindow -j",
            "monitors": "hyprctl monitors -j",
            "focus": f"hyprctl dispatch focuswindow {args}",
            "move": f"hyprctl dispatch movewindow {args}",
            "resize": f"hyprctl dispatch resizeactive {args}",
            "workspace": f"hyprctl dispatch workspace {args}",
            "dispatch": f"hyprctl dispatch {args}",
            "kill": "hyprctl dispatch killactive",
            "fullscreen": "hyprctl dispatch fullscreen",
            "float": "hyprctl dispatch togglefloating",
        }

        if action not in cmd_map:
            available = ", ".join(cmd_map.keys())
            return f"Unknown action: {action}. Available: {available}"

        cmd = cmd_map[action]

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)

            output = ""
            if stdout:
                output = stdout.decode(errors="replace")
            if stderr and proc.returncode != 0:
                output += stderr.decode(errors="replace")

            if not output.strip():
                return "(done — no output)"

            # For JSON outputs, pretty-format key info
            if action in ("windows", "workspaces", "active", "monitors"):
                return self._format_json(action, output)

            return output.strip()

        except asyncio.TimeoutError:
            return "Error: hyprctl command timed out."
        except Exception as e:
            return f"Error: {str(e)}. Make sure hyprctl is available (Hyprland running)."

    def _format_json(self, action: str, raw: str) -> str:
        """Format JSON output into human-readable text."""
        import json
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw[:2000]

        if action == "windows" and isinstance(data, list):
            lines = []
            for w in data:
                title = w.get("title", "untitled")[:50]
                cls = w.get("class", "")
                ws = w.get("workspace", {}).get("name", "?")
                size = w.get("size", [0, 0])
                lines.append(f"[ws:{ws}] {cls} — {title} ({size[0]}x{size[1]})")
            return "\n".join(lines) or "(no windows)"

        if action == "active":
            title = data.get("title", "none")
            cls = data.get("class", "")
            size = data.get("size", [0, 0])
            pos = data.get("at", [0, 0])
            return f"Active: {cls} — {title}\nSize: {size[0]}x{size[1]} at ({pos[0]},{pos[1]})"

        if action == "workspaces" and isinstance(data, list):
            lines = []
            for ws in data:
                name = ws.get("name", "?")
                windows = ws.get("windows", 0)
                lines.append(f"Workspace {name}: {windows} window(s)")
            return "\n".join(lines)

        if action == "monitors" and isinstance(data, list):
            lines = []
            for m in data:
                name = m.get("name", "?")
                res = f"{m.get('width', '?')}x{m.get('height', '?')}"
                lines.append(f"Monitor {name}: {res}")
            return "\n".join(lines)

        return raw[:2000]
