"""OpenAIAgenticProvider: openai SDK client for /v1/chat/completions with tool calling."""

from __future__ import annotations

import concurrent.futures
import json
from pathlib import Path
from typing import Optional, Any

from openai import OpenAI

from .base import ModelProvider
from ._api_key import load_api_key
from ..brave_search import BraveSearchClient


_WEBSEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "WebSearch",
        "description": "Search the web for current events, facts, or context relevant to the newsletter.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."}
            },
            "required": ["query"],
        },
    },
}


class OpenAIAgenticProvider(ModelProvider):
    """Uses the openai Python SDK to call a /v1/chat/completions server with tools.

    Supported generate() kwargs:
        timeout (int): overall request timeout in seconds (default 120)
        max_turns (int): max conversation turns; returns max_turns_exceeded (default 10)
        max_tool_calls_total (int): cumulative tool-call ceiling (default 8)
        tool_timeout_seconds (int): per-tool execution deadline (default 30)
        allowed_tools (str): comma-separated tool names to enable (e.g. "WebSearch")
        system_prompt (str): if provided, prepended as the first system message
    """

    @property
    def name(self) -> str:
        return "openai_agentic"

    def __init__(self, config: dict, repo_root: Optional[Path] = None):
        super().__init__(config)
        base_url = config.get("base_url", "http://localhost:1234/v1")
        api_key = config.get("api_key", "not-needed")
        self.model = config.get("model")
        self.repo_root = repo_root
        self._max_turns = config.get("max_turns", 10)
        self._max_tool_calls_total = config.get("max_tool_calls_total", 8)
        self._tool_timeout_seconds = config.get("tool_timeout_seconds", 30)

        if not self.model:
            raise ValueError("OpenAIAgenticProvider requires 'model' in config")

        if "minimax.io" in base_url and (api_key == "not-needed" or api_key == ""):
            api_key = load_api_key("MINIMAX_API_KEY", repo_root)

        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self._brave_client: Optional[BraveSearchClient] = None

    def _get_brave_client(self) -> BraveSearchClient:
        if self._brave_client is None:
            key = load_api_key("BRAVE_API_KEY", self.repo_root)
            self._brave_client = BraveSearchClient(api_key=key)
        return self._brave_client

    def _run_search(self, query: str) -> list:
        """Execute Brave search. Isolated for timeout wrapping and unit test patching."""
        return self._get_brave_client().search(q=query, count=5)

    def _execute_tool(self, tool_call: Any, timeout_seconds: int = 30) -> str:
        """Execute a single tool call. Always returns a JSON string with a stable shape."""
        name = tool_call.function.name
        try:
            args = json.loads(tool_call.function.arguments)
        except Exception:
            return json.dumps({"error": "invalid_arguments"})

        if name == "WebSearch":
            query = args.get("query", "")
            if not query:
                return json.dumps({"query": "", "error": "invalid_arguments"})

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._run_search, query)
                try:
                    results = future.result(timeout=timeout_seconds)
                except concurrent.futures.TimeoutError:
                    return json.dumps({"query": query, "error": "timeout"})
                except Exception:
                    return json.dumps({"query": query, "error": "search_failed"})

            truncated = [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": (r.get("snippet") or "")[:300],
                }
                for r in results
            ]
            return json.dumps({"query": query, "results": truncated})

        return json.dumps({"error": f"unknown_tool: {name}"})

    def generate(self, prompt: str, **kwargs) -> dict:
        timeout = kwargs.get("timeout", 120)
        max_turns = kwargs.get("max_turns", self._max_turns)
        max_tool_calls_total = kwargs.get("max_tool_calls_total", self._max_tool_calls_total)
        tool_timeout = kwargs.get("tool_timeout_seconds", self._tool_timeout_seconds)
        allowed_tools = kwargs.get("allowed_tools", "")
        system_prompt = kwargs.get("system_prompt")

        active_tools = []
        if allowed_tools and "WebSearch" in allowed_tools:
            active_tools.append(_WEBSEARCH_SCHEMA)

        messages: list = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        tool_calls_count = 0

        for _turn in range(max_turns):
            api_kwargs: dict = {
                "model": self.model,
                "messages": messages,
                "timeout": timeout,
            }
            if active_tools:
                api_kwargs["tools"] = active_tools

            try:
                response = self.client.chat.completions.create(**api_kwargs)
            except Exception:
                return {"result": "", "error": "provider_error"}

            choice = response.choices[0]
            message = choice.message

            # Build a plain dict — OpenAI SDK returns Pydantic objects; third-party
            # endpoints need plain dicts in subsequent turns.
            msg_dict: dict = {"role": "assistant", "content": message.content}
            if message.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ]
            messages.append(msg_dict)

            if choice.finish_reason == "tool_calls" and message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls_count += 1
                    if tool_calls_count > max_tool_calls_total:
                        return {"result": "", "error": "max_tool_calls_exceeded"}
                    result_str = self._execute_tool(tc, timeout_seconds=tool_timeout)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": result_str,
                    })
            elif message.content:
                return {"result": message.content}
            else:
                return {"result": "", "error": "provider_error"}

        return {"result": "", "error": "max_turns_exceeded"}
