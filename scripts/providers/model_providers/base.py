"""ModelProvider ABC and interfaces."""

from abc import ABC, abstractmethod
from typing import Optional


class ModelProvider(ABC):
    """Base class for all model providers."""

    def __init__(self, config: Optional[dict] = None) -> None:
        """Initialize with optional config dict."""
        self._config = config or {}

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier, e.g. 'claude', 'openai_compatible'."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> dict:
        """Execute a prompt against the model. Returns dict with 'result' key (raw model output).

        The caller (ranking_stage, content_stage) is responsible for:
        - Constructing the prompt in the format expected by this provider
        - Interpreting and parsing the result
        - Handling task-specific error recovery (e.g. fallback to filtered ordering in ranking)

        The provider only handles the mechanics of invoking the model.

        Recognized kwargs:
        - timeout (int): seconds before timeout (default 120)
        - max_retries (int): number of retry attempts on failure (default 2)
        - base_delay (float): initial backoff delay in seconds (default 2.0, CLI only)
        - max_turns (int): max turns for CLI (default varies by caller; Mode A uses 10)
        - allowed_tools (str): comma-separated tool names for CLI (e.g. "WebSearch,WebFetch"; Mode A only)

        On error, result dict includes an "error" key describing the failure, e.g.
        {"result": "", "error": "timeout"} or {"result": "", "error": "exit 1"}.

        Note: OpenAICompatibleProvider does not support tools or max_turns. Mode A
        (integrated search) requires a tool-capable provider (only ClaudeProvider currently)."
        """
