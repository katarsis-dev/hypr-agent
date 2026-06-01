"""Web search tool — uses DuckDuckGo (no API key needed)."""

from __future__ import annotations

from typing import Any

from src.config import config


class SearchTool:
    name = "web_search"
    description = "Search the web using DuckDuckGo. Returns top results with titles, URLs, and snippets."
    input_schema = '{"query": "search query", "max_results": 5}'

    async def execute(self, **kwargs: Any) -> str:
        query = kwargs.get("query") or kwargs.get("input", "")
        max_results = int(kwargs.get("max_results", 5))

        if not query:
            return "Error: No search query provided."

        if not config.agent.allow_web_search:
            return "Error: Web search is disabled in configuration."

        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return (
                "Error: duckduckgo-search not installed. "
                "Run: pip install duckduckgo-search"
            )

        try:
            results: list[str] = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(
                        f"**{r['title']}**\n"
                        f"  URL: {r['href']}\n"
                        f"  {r['body']}"
                    )

            if not results:
                return f"No results found for: {query}"
            return "\n\n".join(results)

        except Exception as e:
            return f"Search error: {str(e)}"
