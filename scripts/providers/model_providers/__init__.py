"""model_providers: pluggable model provider factory."""

from .base import ModelProvider
from .claude import ClaudeProvider
from .openai_compatible import OpenAICompatibleProvider

PROVIDER_MAP = {
    "claude": ClaudeProvider,
    "openai_compatible": OpenAICompatibleProvider,
}


def make_provider(config: dict) -> ModelProvider:
    """Instantiate a ModelProvider from a config dict.

    Config must contain:
        provider (str): one of 'claude', 'openai_compatible'

    Provider-specific required fields:
        claude: model (e.g. 'sonnet', 'opus')
        openai_compatible: model, base_url (optional with default)

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
    return PROVIDER_MAP[provider_type](config)


__all__ = ["ModelProvider", "ClaudeProvider", "OpenAICompatibleProvider", "make_provider", "PROVIDER_MAP"]