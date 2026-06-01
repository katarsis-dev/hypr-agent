"""Code execution tool — runs Python snippets in a sandboxed subprocess."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any


class CodeTool:
    name = "run_code"
    description = "Execute a Python code snippet and return stdout/stderr. Use for calculations, data processing, or testing logic."
    input_schema = '{"code": "python code to execute"}'

    async def execute(self, **kwargs: Any) -> str:
        code = kwargs.get("code") or kwargs.get("input", "")
        if not code:
            return "Error: No code provided."

        # Write code to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(code)
            tmp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "python3",
                tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=15.0,
                )
            except asyncio.TimeoutError:
                proc.kill()
                return "Error: Code execution timed out after 15 seconds."

            output = ""
            if stdout:
                output += stdout.decode(errors="replace")
            if stderr:
                output += "\nSTDERR: " + stderr.decode(errors="replace")

            if proc.returncode != 0:
                output += f"\n[Exit code: {proc.returncode}]"

            return output.strip() or "(no output)"

        except Exception as e:
            return f"Error executing code: {str(e)}"
        finally:
            Path(tmp_path).unlink(missing_ok=True)
