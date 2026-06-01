"""Async HTTP client for llama-server (OpenAI-compatible API)."""

from __future__ import annotations

from typing import AsyncGenerator

import httpx

from src.config import config


class LLMClient:
    """Talks to llama-server's OpenAI-compatible completion endpoint."""

    def __init__(self) -> None:
        self.base_url = (
            f"http://{config.llm.server.host}:{config.llm.server.port}"
        )
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(180.0))
        self._cached_system: str | None = None

    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int = 2048,
        stop: list[str] | None = None,
    ) -> str:
        """Generate a completion (non-streaming)."""
        messages = self._build_messages(prompt, system)

        payload = {
            "messages": messages,
            "temperature": temperature or config.agent.temperature,
            "top_p": config.agent.top_p,
            "repeat_penalty": config.agent.repeat_penalty,
            "max_tokens": max_tokens,
            "stream": False,
            "cache_prompt": True,
        }
        if stop:
            payload["stop"] = stop

        resp = await self._client.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def generate_stream(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int = 2048,
        stop: list[str] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Generate a completion with streaming tokens."""
        messages = self._build_messages(prompt, system)

        payload = {
            "messages": messages,
            "temperature": temperature or config.agent.temperature,
            "top_p": config.agent.top_p,
            "repeat_penalty": config.agent.repeat_penalty,
            "max_tokens": max_tokens,
            "stream": True,
            "cache_prompt": True,
        }
        if stop:
            payload["stop"] = stop

        async with self._client.stream(
            "POST",
            f"{self.base_url}/v1/chat/completions",
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    chunk = line[6:]
                    if chunk.strip() == "[DONE]":
                        break
                    import json
                    data = json.loads(chunk)
                    delta = data["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content

    def _build_messages(
        self, prompt: str, system: str,
    ) -> list[dict[str, str]]:
        """Build message list, caching the system prompt for reuse."""
        messages: list[dict[str, str]] = []
        if system:
            self._cached_system = system
            messages.append({"role": "system", "content": system})
        elif self._cached_system:
            messages.append({"role": "system", "content": self._cached_system})
        messages.append({"role": "user", "content": prompt})
        return messages

    async def health_check(self) -> bool:
        """Check if llama-server is reachable."""
        try:
            resp = await self._client.get(f"{self.base_url}/health")
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def close(self) -> None:
        await self._client.aclose()


llm_client = LLMClient()
