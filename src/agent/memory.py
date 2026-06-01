"""Conversation memory — JSON file-based for zero overhead."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "conversations"


class ConversationMemory:
    """Stores conversation history as JSON files."""

    def __init__(self, conversation_id: str | None = None) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.conversation_id = conversation_id or f"conv_{int(time.time())}"
        self.file_path = DATA_DIR / f"{self.conversation_id}.json"
        self.messages: list[dict[str, Any]] = []
        if self.file_path.exists():
            self.messages = json.loads(self.file_path.read_text())

    def add_user_message(self, content: str) -> None:
        self.messages.append({
            "role": "user",
            "content": content,
            "timestamp": time.time(),
        })
        self._save()

    def add_agent_step(
        self,
        thought: str,
        action: str | None = None,
        action_input: str | None = None,
        observation: str | None = None,
        final_answer: str | None = None,
    ) -> None:
        step: dict[str, Any] = {
            "role": "agent",
            "thought": thought,
            "timestamp": time.time(),
        }
        if action:
            step["action"] = action
            step["action_input"] = action_input
        if observation:
            step["observation"] = observation
        if final_answer:
            step["final_answer"] = final_answer
        self.messages.append(step)
        self._save()

    def get_context_window(self, max_messages: int = 20) -> str:
        """Build context string from recent messages for the LLM."""
        recent = self.messages[-max_messages:]
        parts: list[str] = []
        for msg in recent:
            if msg["role"] == "user":
                parts.append(f"USER: {msg['content']}")
            elif msg["role"] == "agent":
                if msg.get("thought"):
                    parts.append(f"THOUGHT: {msg['thought']}")
                if msg.get("action"):
                    parts.append(f"ACTION: {msg['action']}")
                    parts.append(f"ACTION_INPUT: {msg['action_input']}")
                if msg.get("observation"):
                    parts.append(f"OBSERVATION: {msg['observation']}")
                if msg.get("final_answer"):
                    parts.append(f"FINAL_ANSWER: {msg['final_answer']}")
        return "\n".join(parts)

    def list_conversations(self) -> list[dict[str, Any]]:
        """List all saved conversations."""
        convos = []
        for f in sorted(DATA_DIR.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text())
                first_msg = next(
                    (m["content"] for m in data if m["role"] == "user"), "Empty"
                )
                convos.append({
                    "id": f.stem,
                    "preview": first_msg[:80],
                    "messages": len(data),
                    "last_updated": data[-1].get("timestamp", 0) if data else 0,
                })
            except (json.JSONDecodeError, IndexError):
                continue
        return convos

    def _save(self) -> None:
        self.file_path.write_text(json.dumps(self.messages, indent=2))
