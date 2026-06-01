"""Terminal CLI for hypr-agent — single command + interactive REPL."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

# ANSI color codes — no dependencies needed
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
PURPLE = "\033[35m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
CYAN = "\033[36m"
RED = "\033[31m"
GRAY = "\033[90m"


def _format_input(action_input: Any) -> str:
    if action_input is None:
        return ""
    if isinstance(action_input, dict):
        return json.dumps(action_input, ensure_ascii=False)
    return str(action_input)


async def run_agent(user_input: str, conversation_id: str | None = None) -> str | None:
    """Run the agent loop and print events to the terminal. Returns conversation ID."""
    from src.agent.loop import AgentLoop

    agent = AgentLoop(conversation_id=conversation_id)
    conv_id = agent.memory.conversation_id
    current_line_dirty = False

    async for event in agent.run_events(user_input):
        etype = event.type

        if etype == "status":
            content = event.data.get("content", "")
            step = event.data.get("step", "")
            max_steps = event.data.get("max_steps", "")
            step_info = f" [{step}/{max_steps}]" if step else ""
            # Overwrite line
            sys.stdout.write(f"\r{GRAY}{content}{step_info}{RESET}  ")
            sys.stdout.flush()
            current_line_dirty = True

        elif etype == "thinking_delta":
            if current_line_dirty:
                sys.stdout.write("\r\033[K")  # clear status line
                sys.stdout.write(f"{PURPLE}{BOLD}THOUGHT:{RESET} ")
                current_line_dirty = False
            token = event.data.get("content", "")
            sys.stdout.write(f"{DIM}{token}{RESET}")
            sys.stdout.flush()

        elif etype == "thought":
            # Finalize — replace streamed tokens with parsed thought
            content = event.data.get("content", "")
            duration = event.data.get("duration", 0)
            if current_line_dirty:
                sys.stdout.write("\r\033[K")
                current_line_dirty = False
            else:
                # Clear the streamed tokens and rewrite clean
                sys.stdout.write("\r\033[K")
            print(f"{PURPLE}{BOLD}THOUGHT:{RESET} {content} {GRAY}({duration}s){RESET}")

        elif etype == "action_start":
            if current_line_dirty:
                sys.stdout.write("\r\033[K")
                current_line_dirty = False
            action = event.data.get("action", "")
            action_input = event.data.get("action_input")
            input_str = _format_input(action_input)
            input_preview = input_str[:120] + "..." if len(input_str) > 120 else input_str
            sys.stdout.write(f"{YELLOW}{BOLD}ACTION:{RESET}  {action}({input_preview}) ")
            sys.stdout.write(f"{GRAY}running...{RESET}")
            sys.stdout.flush()
            current_line_dirty = True

        elif etype == "observation":
            if current_line_dirty:
                sys.stdout.write("\r\033[K")
                current_line_dirty = False
            action = event.data.get("action", "")
            content = event.data.get("content", "")
            duration = event.data.get("duration", 0)
            # Truncate long output for terminal
            if len(content) > 500:
                content = content[:500] + "\n...[truncated]"
            print(f"{YELLOW}{BOLD}ACTION:{RESET}  {action} {GRAY}({duration}s){RESET}")
            print(f"{GREEN}{BOLD}RESULT:{RESET}  {DIM}{content}{RESET}")

        elif etype == "final_answer":
            if current_line_dirty:
                sys.stdout.write("\r\033[K")
                current_line_dirty = False
            content = event.data.get("content", "")
            duration = event.data.get("duration", 0)
            total = event.data.get("total_duration", 0)
            time_str = f"{duration}s"
            if total:
                time_str += f" / total {total}s"
            print(f"\n{CYAN}{BOLD}ANSWER:{RESET}  {content} {GRAY}({time_str}){RESET}\n")

        elif etype == "error":
            if current_line_dirty:
                sys.stdout.write("\r\033[K")
                current_line_dirty = False
            content = event.data.get("content", "")
            duration = event.data.get("duration", 0)
            print(f"{RED}{BOLD}ERROR:{RESET}   {content} {GRAY}({duration}s){RESET}")

    return conv_id


async def interactive_repl() -> None:
    """Interactive REPL mode — chat with the agent in your terminal."""
    print(f"{CYAN}{BOLD}")
    print(r" _                                                _   ")
    print(r"| |__  _   _ _ __  _ __       __ _  __ _  ___ _ __ | |_ ")
    print(r"| '_ \| | | | '_ \| '__|____ / _` |/ _` |/ _ \ '_ \| __|")
    print(r"| | | | |_| | |_) | | |_____| (_| | (_| |  __/ | | | |_ ")
    print(r"|_| |_|\__, | .__/|_|        \__,_|\__, |\___|_| |_|\__|")
    print(r"       |___/|_|                    |___/                 ")
    print(f"{RESET}")
    print(f"{DIM}Local agentic AI — type your task, or 'quit' to exit.{RESET}")
    print(f"{DIM}Commands: /new (new conversation), /quit (exit){RESET}")
    print()

    conversation_id = None

    while True:
        try:
            user_input = input(f"{BOLD}hypr-agent>{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Bye!{RESET}")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
            print(f"{DIM}Bye!{RESET}")
            break

        if user_input.lower() in ("/new", "/reset"):
            conversation_id = None
            print(f"{DIM}Started new conversation.{RESET}\n")
            continue

        conversation_id = await run_agent(user_input, conversation_id=conversation_id)


async def single_command(task: str) -> None:
    """Run a single task and exit."""
    await run_agent(task)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="hypr-agent",
        description="Local agentic AI — terminal interface",
    )
    parser.add_argument(
        "task",
        nargs="*",
        help='Task to run (e.g., hypr-agent "list files in ~/Downloads")',
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Start interactive REPL mode",
    )
    parser.add_argument(
        "-c", "--conversation",
        type=str,
        default=None,
        help="Resume a specific conversation by ID",
    )

    args = parser.parse_args()

    if args.interactive or not args.task:
        # Interactive REPL
        asyncio.run(interactive_repl())
    else:
        # Single command
        task = " ".join(args.task)
        asyncio.run(single_command(task))


if __name__ == "__main__":
    main()
