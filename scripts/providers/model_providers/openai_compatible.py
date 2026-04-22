"""OpenAICompatibleProvider: openai SDK client for any /v1/chat/completions server."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from openai import OpenAI

from .base import ModelProvider


def _load_minimax_api_key(repo_root: Optional[Path] = None) -> str:
    """Load MINIMAX_API_KEY from .env file or environment."""
    import os

    if repo_root:
        env_path = repo_root / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("MINIMAX_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    key = os.environ.get("MINIMAX_API_KEY", "")
    if not key:
        raise RuntimeError("MINIMAX_API_KEY not found in .env or environment")
    return key


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
        # MiniMax uses OpenAI-compatible endpoint; load key from env if needed
        if "minimax.io" in base_url and (api_key == "not-needed" or api_key == ""):
            api_key = _load_minimax_api_key(repo_root)
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def generate(self, prompt: str, **kwargs) -> dict:
        timeout = kwargs.get("timeout", 120)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
        )
        return {"result": response.choices[0].message.content}
