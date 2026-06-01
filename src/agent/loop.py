"""ReAct agent loop — think, act, observe, repeat."""

from __future__ import annotations

import json
import re
import time
from typing import Any, AsyncGenerator

from src.agent.memory import ConversationMemory
from src.agent.prompt import TOOL_DESCRIPTION_TEMPLATE, build_system_prompt
from src.config import config
from src.llm.client import llm_client
from src.tools import tool_registry


class AgentStep:
    """Represents a single step in the agent loop."""

    def __init__(
        self,
        thought: str = "",
        action: str | None = None,
        action_input: Any = None,
        observation: str | None = None,
        final_answer: str | None = None,
        error: str | None = None,
    ) -> None:
        self.thought = thought
        self.action = action
        self.action_input = action_input
        self.observation = observation
        self.final_answer = final_answer
        self.error = error
        self.duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"thought": self.thought}
        if self.action:
            d["action"] = self.action
            d["action_input"] = self.action_input
        if self.observation is not None:
            d["observation"] = self.observation
        if self.final_answer is not None:
            d["final_answer"] = self.final_answer
        if self.error:
            d["error"] = self.error
        d["duration"] = round(self.duration, 2)
        return d


class AgentLoop:
    """The core ReAct agent loop."""

    def __init__(self, conversation_id: str | None = None) -> None:
        self.memory = ConversationMemory(conversation_id)
        self.max_steps = config.agent.max_steps

    def _build_system_prompt(self) -> str:
        tools_desc = ""
        for name, tool in tool_registry.items():
            tools_desc += TOOL_DESCRIPTION_TEMPLATE.format(
                name=name,
                description=tool.description,
                input_schema=tool.input_schema,
            )
        return build_system_prompt(tools_desc)

    def _parse_response(self, response: str) -> AgentStep:
        """Parse LLM response into structured step."""
        step = AgentStep()

        # Extract THOUGHT
        thought_match = re.search(
            r"THOUGHT:\s*(.+?)(?=\n(?:ACTION|FINAL_ANSWER):|\Z)",
            response,
            re.DOTALL,
        )
        if thought_match:
            step.thought = thought_match.group(1).strip()

        # Check for FINAL_ANSWER
        final_match = re.search(r"FINAL_ANSWER:\s*(.+)", response, re.DOTALL)
        if final_match:
            step.final_answer = final_match.group(1).strip()
            return step

        # Check for ACTION
        action_match = re.search(r"ACTION:\s*(\w+)", response)
        if action_match:
            step.action = action_match.group(1).strip()

            # Extract ACTION_INPUT
            input_match = re.search(
                r"ACTION_INPUT:\s*(.+?)(?=\n(?:THOUGHT|ACTION|FINAL_ANSWER):|\Z)",
                response,
                re.DOTALL,
            )
            if input_match:
                raw_input = input_match.group(1).strip()
                try:
                    step.action_input = json.loads(raw_input)
                except json.JSONDecodeError:
                    step.action_input = raw_input

        return step

    async def _execute_tool(self, action: str, action_input: Any) -> str:
        """Execute a tool and return the result."""
        if action not in tool_registry:
            return f"Error: Unknown tool '{action}'. Available: {list(tool_registry.keys())}"

        tool = tool_registry[action]
        try:
            if isinstance(action_input, dict):
                result = await tool.execute(**action_input)
            elif isinstance(action_input, str):
                result = await tool.execute(input=action_input)
            else:
                result = await tool.execute(input=str(action_input))

            # Truncate long results
            if len(result) > config.agent.max_output_chars:
                result = result[: config.agent.max_output_chars] + "\n...[truncated]"
            return result
        except Exception as e:
            return f"Error executing {action}: {str(e)}"

    async def run(self, user_input: str) -> AsyncGenerator[AgentStep, None]:
        """Run the agent loop, yielding each step as it happens."""
        self.memory.add_user_message(user_input)

        for step_num in range(self.max_steps):
            start = time.time()

            # Build prompt with conversation history
            context = self.memory.get_context_window()
            prompt = f"{context}\n\nContinue. Respond with THOUGHT then ACTION or FINAL_ANSWER."

            # Get LLM response
            try:
                response = await llm_client.generate(
                    prompt=prompt,
                    system=self._build_system_prompt(),
                )
            except Exception as e:
                step = AgentStep(error=f"LLM error: {str(e)}")
                step.duration = time.time() - start
                yield step
                return

            # Parse response
            step = self._parse_response(response)
            step.duration = time.time() - start

            # If we got a final answer, we're done
            if step.final_answer:
                self.memory.add_agent_step(
                    thought=step.thought,
                    final_answer=step.final_answer,
                )
                yield step
                return

            # If we got an action, execute it
            if step.action:
                obs_start = time.time()
                observation = await self._execute_tool(step.action, step.action_input)
                step.observation = observation
                step.duration += time.time() - obs_start

                self.memory.add_agent_step(
                    thought=step.thought,
                    action=step.action,
                    action_input=json.dumps(step.action_input)
                    if isinstance(step.action_input, dict)
                    else str(step.action_input),
                    observation=observation,
                )
                yield step
            else:
                # No action and no final answer — the model is confused
                step.error = "No valid action or final answer parsed from response."
                self.memory.add_agent_step(thought=step.thought or response)
                yield step
                # Give it one more chance
                continue

        # Max steps reached
        yield AgentStep(
            thought="Maximum steps reached.",
            final_answer="I've reached the maximum number of steps. Here's what I've done so far — please check the steps above.",
        )
