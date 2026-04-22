"""ClaudeProvider: CLI subprocess model provider with exponential backoff."""

from __future__ import annotations

import json
import subprocess
import time

from .base import ModelProvider


class ClaudeProvider(ModelProvider):
    """Uses the `claude -p` CLI subprocess to avoid API billing.
    Implements custom retry with exponential backoff for transient failures.
    """

    @property
    def name(self) -> str:
        return "claude"

    def __init__(self, config: dict):
        super().__init__(config)
        self.model = config.get("model")
        if not self.model:
            raise ValueError(
                "ClaudeProvider requires 'model' in config (e.g. 'sonnet', 'opus')"
            )

    def generate(self, prompt: str, **kwargs) -> dict:
        timeout = kwargs.get("timeout", 120)
        max_retries = kwargs.get("max_retries", 2)
        base_delay = kwargs.get("base_delay", 2.0)
        max_turns = kwargs.get("max_turns", 2)
        allowed_tools = kwargs.get("allowed_tools")

        for attempt in range(max_retries + 1):
            try:
                args = [
                    "claude", "-p", prompt,
                    "--output-format", "json",
                    "--model", self.model,
                    "--max-turns", str(max_turns),
                ]
                if allowed_tools:
                    args.extend(["--allowedTools", allowed_tools])

                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                if attempt < max_retries:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                return {"result": "", "error": "timeout"}

            if result.returncode != 0:
                if attempt < max_retries:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                return {"result": "", "error": f"exit {result.returncode}"}

            try:
                outer = json.loads(result.stdout)
                result_text = outer.get("result", "")
                if not result_text:
                    raise ValueError("content provider returned empty result")
                return {"result": result_text}
            except (json.JSONDecodeError, KeyError, ValueError):
                if attempt < max_retries:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                return {"result": "", "error": "parse_error"}

        return {"result": "", "error": "exhausted_retries"}
