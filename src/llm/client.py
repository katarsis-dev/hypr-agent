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

    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int = 2048,
        stop: list[str] | None = None,
    ) -> str:
        """Generate a completion (non-streaming)."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "temperature": temperature or config.agent.temperature,
            "top_p": config.agent.top_p,
            "repeat_penalty": config.agent.repeat_penalty,
            "max_tokens": max_tokens,
            "stream": False,
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
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "temperature": temperature or config.agent.temperature,
            "top_p": config.agent.top_p,
            "repeat_penalty": config.agent.repeat_penalty,
            "max_tokens": max_tokens,
            "stream": True,
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
