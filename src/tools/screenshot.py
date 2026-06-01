"""Screenshot tool — capture screen/region on Hyprland (grim + slurp)."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any


class ScreenshotTool:
    name = "screenshot"
    description = "Take a screenshot of the full screen or a selected region. Saves to ~/Pictures/screenshots/. Requires grim (and slurp for region select) on Wayland/Hyprland."
    input_schema = '{"action": "full|region|window", "output": "optional output path"}'

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "full")
        output = kwargs.get("output", "")

        # Default output path
        if not output:
            screenshots_dir = Path.home() / "Pictures" / "screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output = str(screenshots_dir / f"screenshot_{timestamp}.png")

        if action == "full":
            cmd = f"grim {output}"
        elif action == "region":
            cmd = f'grim -g "$(slurp)" {output}'
        elif action == "window":
            # Capture the active window via hyprctl
            cmd = f'grim -g "$(hyprctl activewindow -j | jq -r \'.at[0],\" \", .at[1],\" \",.size[0],\" \",.size[1]\' | tr \'\\n\' \' \' | awk \'{{print $1\",\"$2\" \"$3\"x\"$4}}\')" {output}'
        else:
            return f"Unknown action: {action}. Use: full, region, window"

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)

            if proc.returncode == 0:
                return f"Screenshot saved to: {output}"
            else:
                error = stderr.decode(errors="replace") if stderr else "unknown error"
                return f"Error taking screenshot: {error}\nMake sure grim is installed: pacman -S grim slurp"
        except asyncio.TimeoutError:
            return "Error: Screenshot timed out (region selection cancelled?)."
        except Exception as e:
            return f"Error: {str(e)}"
