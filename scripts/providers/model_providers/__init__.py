"""model_providers: pluggable model provider factory."""

from pathlib import Path
from typing import Optional

from .base import ModelProvider
from .claude import ClaudeProvider
from .openai_compatible import OpenAICompatibleProvider
from .openai_agentic import OpenAIAgenticProvider

PROVIDER_MAP = {
    "claude": ClaudeProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "openai_agentic": OpenAIAgenticProvider,
}


def make_provider(config: dict, repo_root: Optional[Path] = None) -> ModelProvider:
    """Instantiate a ModelProvider from a config dict.

    Config must contain:
        provider (str): one of 'claude', 'openai_compatible', 'openai_agentic'

    Provider-specific required fields:
        claude: model (e.g. 'claude-sonnet-4-6')
        openai_compatible: model, base_url (optional, defaults to localhost:1234)
        openai_agentic: model, base_url (optional, defaults to localhost:1234)

    Raises:
        ValueError: if provider is missing, unknown, or model is required but absent.
    """
    provider_type = config.get("provider")
    if not provider_type:
        raise ValueError("Provider config missing 'provider' key")
    if provider_type not in PROVIDER_MAP:
        raise ValueError(
            f"Unknown provider '{provider_type}'. "
            f"Available: {list(PROVIDER_MAP.keys())}"
        )
    provider_cls = PROVIDER_MAP[provider_type]
    if repo_root is None:
        return provider_cls(config)
    try:
        return provider_cls(config, repo_root=repo_root)
    except TypeError as exc:
        if "repo_root" not in str(exc):
            raise
        return provider_cls(config)


__all__ = ["ModelProvider", "ClaudeProvider", "OpenAICompatibleProvider", "OpenAIAgenticProvider", "make_provider", "PROVIDER_MAP"]