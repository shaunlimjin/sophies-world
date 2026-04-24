"""OpenAICompatibleProvider: openai SDK client for any /v1/chat/completions server."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from openai import OpenAI

from .base import ModelProvider
from ._api_key import load_api_key


class OpenAICompatibleProvider(ModelProvider):
    """Uses the openai Python SDK to call any server implementing /v1/chat/completions.
    Covers Ollama, LM Studio, MiniMax, and any OpenAI-API-compatible endpoint.
    """

    @property
    def name(self) -> str:
        return "openai_compatible"

    def __init__(self, config: dict, repo_root: Optional[Path] = None):
        super().__init__(config)
        base_url = config.get("base_url", "http://localhost:1234/v1")
        api_key = config.get("api_key", "not-needed")
        self.model = config.get("model")
        if not self.model:
            raise ValueError("OpenAICompatibleProvider requires 'model' in config")
        if "minimax.io" in base_url and (api_key == "not-needed" or api_key == ""):
            api_key = load_api_key("MINIMAX_API_KEY", repo_root)
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def generate(self, prompt: str, **kwargs) -> dict:
        timeout = kwargs.get("timeout", 120)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
        )
        return {"result": response.choices[0].message.content}
