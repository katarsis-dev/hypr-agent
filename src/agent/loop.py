"""ReAct agent loop — think, act, observe, repeat."""

from __future__ import annotations

import json
import re
import time
from typing import Any, AsyncGenerator

from src.agent.memory import ConversationMemory
from src.agent.prompt import TOOL_DESCRIPTION_TEMPLATE, build_fast_prompt, build_system_prompt
from src.config import config
from src.llm.client import llm_client
from src.tools import tool_registry

# Keywords that indicate tools are needed (not just a simple question)
_TOOL_KEYWORDS = {
    "file", "folder", "directory", "list", "read", "write", "create", "delete",
    "run", "execute", "shell", "command", "terminal", "screenshot", "search",
    "git", "commit", "convert", "download", "install", "system", "cpu", "ram",
    "disk", "process", "window", "workspace", "move", "copy", "rename", "find",
    "grep", "open", "save", "edit", "fix", "repair", "debug", "code",
}


class AgentEvent:
    """A granular event emitted during agent execution."""

    def __init__(self, event_type: str, **kwargs: Any) -> None:
        self.type = event_type
        self.data = kwargs

    def to_ws(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"type": self.type}
        msg.update(self.data)
        return msg


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

    def __init__(
        self,
        conversation_id: str | None = None,
        fast_mode: bool | None = None,
    ) -> None:
        self.memory = ConversationMemory(conversation_id)
        self.max_steps = config.agent.max_steps
        self._fast_mode = fast_mode  # None = auto-detect

    def _needs_tools(self, user_input: str) -> bool:
        """Check if a message likely needs tools or is just a simple question."""
        words = set(user_input.lower().split())
        # Attached files always need tools
        if "[attached files:]" in user_input.lower():
            return True
        return bool(words & _TOOL_KEYWORDS)

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
        """Run the agent loop, yielding each step as it happens (legacy)."""
        async for event in self.run_events(user_input):
            if event.type in ("thought", "action", "observation", "final_answer", "error"):
                step = AgentStep()
                if event.type == "thought":
                    step.thought = event.data.get("content", "")
                    step.duration = event.data.get("duration", 0)
                elif event.type == "action":
                    step.action = event.data.get("action", "")
                    step.action_input = event.data.get("action_input")
                    step.duration = event.data.get("duration", 0)
                elif event.type == "observation":
                    step.observation = event.data.get("content", "")
                    step.duration = event.data.get("duration", 0)
                elif event.type == "final_answer":
                    step.final_answer = event.data.get("content", "")
                    step.duration = event.data.get("duration", 0)
                elif event.type == "error":
                    step.error = event.data.get("content", "")
                    step.duration = event.data.get("duration", 0)
                yield step

    async def run_events(self, user_input: str) -> AsyncGenerator[AgentEvent, None]:
        """Run the agent loop, yielding granular events for real-time UI."""
        self.memory.add_user_message(user_input)
        total_start = time.time()

        # Fast mode: skip tools for simple questions
        use_fast = self._fast_mode if self._fast_mode is not None else not self._needs_tools(
            user_input
        )
        if use_fast:
            async for event in self._run_fast(user_input, total_start):
                yield event
            return

        for step_num in range(self.max_steps):
            start = time.time()

            # Status: generating
            yield AgentEvent(
                "status",
                content=f"Thinking... (step {step_num + 1}/{self.max_steps})",
                step=step_num + 1,
                max_steps=self.max_steps,
            )

            # Build prompt
            context = self.memory.get_context_window()
            prompt = f"{context}\n\nContinue. Respond with THOUGHT then ACTION or FINAL_ANSWER."
            system = self._build_system_prompt()

            # Stream LLM response token by token
            full_response = ""
            try:
                async for token in llm_client.generate_stream(
                    prompt=prompt,
                    system=system,
                ):
                    full_response += token
                    yield AgentEvent("thinking_delta", content=token)
            except Exception as e:
                yield AgentEvent(
                    "error",
                    content=f"LLM error: {str(e)}",
                    duration=round(time.time() - start, 2),
                )
                return

            think_duration = round(time.time() - start, 2)

            # Parse the complete response
            step = self._parse_response(full_response)

            # Emit the complete thought
            if step.thought:
                yield AgentEvent(
                    "thought",
                    content=step.thought,
                    duration=think_duration,
                )

            # Final answer
            if step.final_answer:
                self.memory.add_agent_step(
                    thought=step.thought,
                    final_answer=step.final_answer,
                )
                yield AgentEvent(
                    "final_answer",
                    content=step.final_answer,
                    duration=think_duration,
                    total_duration=round(time.time() - total_start, 2),
                )
                return

            # Action execution
            if step.action:
                yield AgentEvent(
                    "action_start",
                    action=step.action,
                    action_input=step.action_input,
                )
                yield AgentEvent(
                    "status",
                    content=f"Running {step.action}...",
                    step=step_num + 1,
                    max_steps=self.max_steps,
                )

                obs_start = time.time()
                observation = await self._execute_tool(
                    step.action, step.action_input
                )
                obs_duration = round(time.time() - obs_start, 2)

                self.memory.add_agent_step(
                    thought=step.thought,
                    action=step.action,
                    action_input=json.dumps(step.action_input)
                    if isinstance(step.action_input, dict)
                    else str(step.action_input),
                    observation=observation,
                )

                yield AgentEvent(
                    "observation",
                    content=observation,
                    action=step.action,
                    duration=obs_duration,
                )
            else:
                # No action and no final answer
                yield AgentEvent(
                    "error",
                    content="No valid action or final answer parsed from response.",
                    duration=think_duration,
                )
                self.memory.add_agent_step(thought=step.thought or full_response)
                continue

        # Max steps reached
        yield AgentEvent(
            "final_answer",
            content="I've reached the maximum number of steps. Here's what I've done so far — please check the steps above.",
            duration=0,
            total_duration=round(time.time() - total_start, 2),
        )

    async def _run_fast(
        self, user_input: str, total_start: float,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Fast path — lightweight prompt, single LLM call, no tool loop."""
        start = time.time()

        yield AgentEvent(
            "status",
            content="Thinking (fast mode)...",
            step=1,
            max_steps=1,
        )

        system = build_fast_prompt()
        context = self.memory.get_context_window()
        prompt = f"{context}\n\nRespond directly."

        full_response = ""
        try:
            async for token in llm_client.generate_stream(
                prompt=prompt,
                system=system,
            ):
                full_response += token
                yield AgentEvent("thinking_delta", content=token)
        except Exception as e:
            yield AgentEvent(
                "error",
                content=f"LLM error: {str(e)}",
                duration=round(time.time() - start, 2),
            )
            return

        duration = round(time.time() - start, 2)
        step = self._parse_response(full_response)

        if step.thought:
            yield AgentEvent("thought", content=step.thought, duration=duration)

        # If the model decided it needs tools anyway, fall back to full mode
        if step.action:
            yield AgentEvent(
                "status",
                content="Switching to full mode (tools needed)...",
                step=1,
                max_steps=self.max_steps,
            )
            self._fast_mode = False
            # Re-run with full tool loop (don't re-add user message)
            for step_num in range(self.max_steps):
                inner_start = time.time()

                yield AgentEvent(
                    "status",
                    content=f"Thinking... (step {step_num + 1}/{self.max_steps})",
                    step=step_num + 1,
                    max_steps=self.max_steps,
                )

                ctx = self.memory.get_context_window()
                full_prompt = f"{ctx}\n\nContinue. Respond with THOUGHT then ACTION or FINAL_ANSWER."
                full_system = self._build_system_prompt()

                resp_text = ""
                try:
                    async for token in llm_client.generate_stream(
                        prompt=full_prompt,
                        system=full_system,
                    ):
                        resp_text += token
                        yield AgentEvent("thinking_delta", content=token)
                except Exception as e:
                    yield AgentEvent(
                        "error",
                        content=f"LLM error: {str(e)}",
                        duration=round(time.time() - inner_start, 2),
                    )
                    return

                inner_duration = round(time.time() - inner_start, 2)
                inner_step = self._parse_response(resp_text)

                if inner_step.thought:
                    yield AgentEvent(
                        "thought", content=inner_step.thought, duration=inner_duration,
                    )

                if inner_step.final_answer:
                    self.memory.add_agent_step(
                        thought=inner_step.thought, final_answer=inner_step.final_answer,
                    )
                    yield AgentEvent(
                        "final_answer",
                        content=inner_step.final_answer,
                        duration=inner_duration,
                        total_duration=round(time.time() - total_start, 2),
                    )
                    return

                if inner_step.action:
                    yield AgentEvent(
                        "action_start",
                        action=inner_step.action,
                        action_input=inner_step.action_input,
                    )
                    obs_start = time.time()
                    observation = await self._execute_tool(
                        inner_step.action, inner_step.action_input,
                    )
                    obs_dur = round(time.time() - obs_start, 2)

                    self.memory.add_agent_step(
                        thought=inner_step.thought,
                        action=inner_step.action,
                        action_input=json.dumps(inner_step.action_input)
                        if isinstance(inner_step.action_input, dict)
                        else str(inner_step.action_input),
                        observation=observation,
                    )
                    yield AgentEvent(
                        "observation",
                        content=observation,
                        action=inner_step.action,
                        duration=obs_dur,
                    )
            return

        answer = step.final_answer or full_response.strip()
        self.memory.add_agent_step(
            thought=step.thought or "",
            final_answer=answer,
        )
        yield AgentEvent(
            "final_answer",
            content=answer,
            duration=duration,
            total_duration=round(time.time() - total_start, 2),
        )
