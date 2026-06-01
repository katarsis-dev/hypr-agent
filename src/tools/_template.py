"""
╔══════════════════════════════════════════════════════════════╗
║  Python Tool Template — copy this to create a new tool       ║
╚══════════════════════════════════════════════════════════════╝

How to add a new Python tool:
1. Copy this file to src/tools/your_tool_name.py
2. Rename the class and fill in name/description/input_schema
3. Implement the execute() method
4. Done! It's auto-discovered on startup. No other changes needed.

Files starting with _ are ignored by auto-discovery.
"""

from __future__ import annotations

from typing import Any


class TemplateTool:
    # The name the agent uses to call this tool
    name = "my_tool"

    # What this tool does — the agent reads this to decide when to use it
    description = "Describe what your tool does here."

    # JSON hint showing what inputs the tool accepts
    input_schema = '{"param1": "description", "param2": "description"}'

    async def execute(self, **kwargs: Any) -> str:
        """Run the tool. kwargs come from the agent's ACTION_INPUT JSON."""
        param1 = kwargs.get("param1", "")
        param2 = kwargs.get("param2", "")

        # Your logic here
        result = f"Got param1={param1}, param2={param2}"

        return result
