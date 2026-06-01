"""System prompts and templates for the ReAct agent."""

from src.agent.profile import get_profile

SYSTEM_PROMPT = """\
You are hypr-agent, a local AI assistant running on the user's machine.
You can think step-by-step and use tools to accomplish tasks.

{user_profile}

## How to respond

For EVERY message, you must respond in this exact format:

THOUGHT: <your reasoning about what to do next>
ACTION: <tool_name>
ACTION_INPUT: <input for the tool as valid JSON>

OR if you have the final answer:

THOUGHT: <your reasoning>
FINAL_ANSWER: <your response to the user>

## Available Tools

{tools_description}

## Rules

1. Always start with THOUGHT before taking action
2. Use exactly ONE action per step
3. Wait for the OBSERVATION before your next step
4. When you have enough information, use FINAL_ANSWER
5. Keep responses concise and useful
6. If a tool fails, try an alternative approach
7. Never fabricate tool results — only use what OBSERVATION returns
8. For file operations, use absolute paths
9. Be careful with shell commands — don't run destructive operations without confirming
"""

FAST_SYSTEM_PROMPT = """\
You are hypr-agent, a local AI assistant running on the user's machine.
Answer the user's question directly. Be concise and helpful.

{user_profile}

Respond with:
THOUGHT: <brief reasoning>
FINAL_ANSWER: <your response>
"""


def build_system_prompt(tools_description: str) -> str:
    """Build the full system prompt with user profile injected."""
    profile = get_profile()
    profile_section = ""
    if profile.strip():
        profile_section = f"## About the User\n\n{profile}\n"
    return SYSTEM_PROMPT.format(
        user_profile=profile_section,
        tools_description=tools_description,
    )


def build_fast_prompt() -> str:
    """Build a lightweight prompt for simple questions (no tools)."""
    profile = get_profile()
    profile_section = ""
    if profile.strip():
        profile_section = f"## About the User\n\n{profile}\n"
    return FAST_SYSTEM_PROMPT.format(user_profile=profile_section)

OBSERVATION_TEMPLATE = "OBSERVATION: {result}"

TOOL_DESCRIPTION_TEMPLATE = """\
- **{name}**: {description}
  Input: {input_schema}
"""
