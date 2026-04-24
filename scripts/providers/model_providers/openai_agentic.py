"""OpenAIAgenticProvider: openai SDK client for /v1/chat/completions with tool calling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from openai import OpenAI

from .base import ModelProvider
from ._api_key import load_api_key
from ..brave_search import BraveSearchClient


class OpenAIAgenticProvider(ModelProvider):
    """Uses the openai Python SDK to call a /v1/chat/completions server with tools.
    Supports a multi-turn agentic loop.
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

    def _execute_tool(self, tool_call: Any) -> str:
        """Execute a requested tool and return the stringified JSON result."""
        name = tool_call.function.name
        try:
            args = json.loads(tool_call.function.arguments)
        except Exception as e:
            return json.dumps({"error": f"Invalid arguments JSON: {e}"})

        if name == "WebSearch":
            query = args.get("query", "")
            if not query:
                return json.dumps({"error": "Missing 'query' parameter"})
            try:
                brave = self._get_brave_client()
                results = brave.search(q=query, count=5)
                return json.dumps({"results": results})
            except Exception as e:
                return json.dumps({"error": f"Search failed: {e}"})
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    def generate(self, prompt: str, **kwargs) -> dict:
        timeout = kwargs.get("timeout", 120)
        max_turns = kwargs.get("max_turns", 10)
        allowed_tools = kwargs.get("allowed_tools", "")
        system_prompt = kwargs.get("system_prompt")

        active_tools = []
        if allowed_tools and "WebSearch" in allowed_tools:
            active_tools.append({
                "type": "function",
                "function": {
                    "name": "WebSearch",
                    "description": "Search the web for current events, facts, or context.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query."
                            }
                        },
                        "required": ["query"]
                    }
                }
            })

        messages: list = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for turn in range(max_turns):
            api_kwargs = {
                "model": self.model,
                "messages": messages,
                "timeout": timeout,
            }
            if active_tools:
                api_kwargs["tools"] = active_tools

            try:
                response = self.client.chat.completions.create(**api_kwargs)
            except Exception as e:
                return {"result": "", "error": str(e)}

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
                # Execute tools
                for tc in message.tool_calls:
                    result_str = self._execute_tool(tc)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": result_str,
                    })
                # Loop continues to next turn
            elif choice.finish_reason in ("stop", "length", None) or not message.tool_calls:
                # Finished
                return {"result": message.content or ""}
            else:
                # Unknown reason, try to return content or stop
                return {"result": message.content or ""}

        return {"result": "", "error": "exhausted_max_turns"}
