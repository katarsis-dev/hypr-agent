"""YAML skill loader — turns simple YAML files into agent tools."""

from __future__ import annotations

import asyncio
import string
from pathlib import Path
from typing import Any

import yaml


class YamlSkill:
    """A tool generated from a YAML skill definition."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.name: str = config["name"]
        self.description: str = config["description"]
        self._commands: dict[str, str] = config.get("commands", {})
        self._default_action: str | None = config.get("default_action")
        self._timeout: int = config.get("timeout", 30)

        # Build input_schema from commands
        actions = list(self._commands.keys())
        if actions:
            self.input_schema = f'{{"action": "{"|".join(actions)}"}}'
        else:
            self.input_schema = '{"input": "text input"}'

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action") or self._default_action
        raw_input = kwargs.get("input", "")

        # If no commands defined, treat as a single-command skill
        if not self._commands:
            return "Error: No commands defined for this skill."

        if action not in self._commands:
            available = ", ".join(self._commands.keys())
            return f"Error: Unknown action '{action}'. Available: {available}"

        # Get the command template and substitute variables
        cmd_template = self._commands[action]
        try:
            cmd = string.Template(cmd_template).safe_substitute(
                input=raw_input, **kwargs
            )
        except (KeyError, ValueError):
            cmd = cmd_template

        # Execute the command
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self._timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                return f"Error: Command timed out after {self._timeout}s."

            output = ""
            if stdout:
                output += stdout.decode(errors="replace")
            if stderr:
                output += "\n" + stderr.decode(errors="replace")
            return output.strip() or "(no output)"

        except Exception as e:
            return f"Error: {str(e)}"


def load_yaml_skill(filepath: Path) -> YamlSkill | None:
    """Load a single YAML skill file."""
    try:
        with open(filepath) as f:
            config = yaml.safe_load(f)
        if not config or "name" not in config or "description" not in config:
            print(f"[hypr-agent] Skipping {filepath.name}: missing 'name' or 'description'")
            return None
        return YamlSkill(config)
    except Exception as e:
        print(f"[hypr-agent] Error loading skill {filepath.name}: {e}")
        return None


def load_yaml_skills_from_dir(skills_dir: Path) -> list[YamlSkill]:
    """Load all YAML skills from a directory. Files starting with _ are skipped."""
    skills: list[YamlSkill] = []
    for filepath in sorted(skills_dir.glob("*.yaml")):
        if filepath.name.startswith("_"):
            continue
        skill = load_yaml_skill(filepath)
        if skill:
            skills.append(skill)
    for filepath in sorted(skills_dir.glob("*.yml")):
        if filepath.name.startswith("_"):
            continue
        skill = load_yaml_skill(filepath)
        if skill:
            skills.append(skill)
    return skills
