# Pluggable Hosted Model Support — Design

## Status

Approved (revised per architectural feedback 2026-04-21).

## Goal

Refactor `hosted_llm_provider.py` so the model (Claude Sonnet vs Opus, MiniMax, future alternatives) can be configured per-child and per-task (synthesis vs. ranking) without code changes.

## Architecture Overview

```
ModelProvider (ABC)
├── ClaudeProvider          → uses anthropic Python SDK, supports model override
├── MiniMaxProvider         → uses anthropic Python SDK, no model param
└── OpenAICompatibleProvider → uses openai Python SDK, supports model override
                               (covers Ollama, LM Studio, and any /v1/chat/completions server)
```

Each provider is a thin, self-contained class that knows how to invoke its underlying SDK or API. The config layer only names the provider and model; the provider handles the mechanics. Pipeline stages own task-specific prompt construction and output parsing.

---

## 1. Provider Interface

```python
from abc import ABC, abstractmethod

class ModelProvider(ABC):
    """Base class for all model providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier, e.g. 'claude', 'minimax', 'openai_compatible'."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> dict:
        """Execute a prompt against the model. Returns dict with 'result' key (raw model output).

        The caller (ranking_stage, content_stage) is responsible for:
        - Constructing the prompt in the format expected by this provider
        - Interpreting and parsing the result
        - Handling task-specific error recovery (e.g. fallback to filtered ordering in ranking)

        The provider only handles the mechanics of invoking the model.
        """
```

`generate()` is generic and task-agnostic. It returns `{"result": "...", ...}` — the raw output that the calling stage then interprets. This decouples the provider from pipeline semantics.

---

## 2. HostedProvider Base (removed)

`HostedProvider` is removed. There is no meaningful shared CLI-building logic once we move to SDKs, and the `supports_model_param` concept does not translate cleanly to SDK-style providers. Each provider implements `generate()` directly.

---

## 3. Concrete Providers

### ClaudeProvider

Uses the official `anthropic` Python SDK.

```python
from anthropic import Anthropic

class ClaudeProvider(ModelProvider):
    name = "claude"

    def __init__(self, config: dict):
        self.model = config.get("model")
        self.client = Anthropic()

    def generate(self, prompt: str, **kwargs) -> dict:
        timeout = kwargs.get("timeout", 120)
        max_retries = kwargs.get("max_retries", 2)

        for attempt in range(max_retries + 1):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=kwargs.get("max_tokens", 4096),
                    messages=[{"role": "user", "content": prompt}],
                    timeout=timeout,
                )
                return {"result": response.content[0].text}
            except Exception as exc:
                if attempt < max_retries:
                    continue
                raise

        return {"result": ""}
```

If `model` is not set in config, raise `ValueError` at instantiation time.

### MiniMaxProvider

Uses the `anthropic` SDK. MiniMax exposes the same API as Anthropic (they are API-compatible).

```python
class MiniMaxProvider(ModelProvider):
    name = "minimax"

    def __init__(self, config: dict):
        api_key = config.get("api_key") or os.environ.get("MINIMAX_API_KEY")
        if not api_key:
            raise ValueError("MiniMaxProvider requires api_key in config or MINIMAX_API_KEY env var")
        self.client = Anthropic(base_url="https://api.minimax.chat/v1", api_key=api_key)
        self.model = config.get("model", "MiniMax-Text-01")

    def generate(self, prompt: str, **kwargs) -> dict:
        # same pattern as ClaudeProvider
```

`model` has a sensible default — no config required if using the default model.

### OpenAICompatibleProvider

Uses the official `openai` Python SDK. Connects to any server implementing the standard `/v1/chat/completions` endpoint (Ollama, LM Studio, etc.).

```python
from openai import OpenAI

class OpenAICompatibleProvider(ModelProvider):
    name = "openai_compatible"

    def __init__(self, config: dict):
        base_url = config.get("base_url", "http://localhost:1234/v1")
        api_key = config.get("api_key", "not-needed")  # most local servers don't require a key
        self.model = config.get("model")
        if not self.model:
            raise ValueError("OpenAICompatibleProvider requires model in config")
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def generate(self, prompt: str, **kwargs) -> dict:
        timeout = kwargs.get("timeout", 120)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
        )
        return {"result": response.choices[0].message.content}
```

`supports_model_param` is always `True` here — the model name is sent in the API payload and is configured dynamically via YAML.

---

## 4. Config Structure

In `config/children/sophie.yaml`:

```yaml
providers:
  synthesis:
    provider: claude
    model: opus
  ranking:
    provider: claude
    model: sonnet

  # Local example (M4 Mac Mini with Ollama):
  # synthesis:
  #   provider: openai_compatible
  #   base_url: http://localhost:1234/v1
  #   model: gemma3:12b
  # ranking:
  #   provider: openai_compatible
  #   base_url: http://localhost:1234/v1
  #   model: qwen3:3b
```

The `type` key is removed — routing is done solely on the `provider` name. No hosted/local distinction needed at the config level.

If `model` is required by a provider but not provided, `ValueError` is raised at startup.

---

## 5. Provider Factory

```python
PROVIDER_MAP = {
    "claude": ClaudeProvider,
    "minimax": MiniMaxProvider,
    "openai_compatible": OpenAICompatibleProvider,
}

def make_provider(config: dict) -> ModelProvider:
    provider_type = config.get("provider")
    if not provider_type:
        raise ValueError("Provider config missing 'provider' key")
    if provider_type not in PROVIDER_MAP:
        raise ValueError(
            f"Unknown provider '{provider_type}'. "
            f"Available: {list(PROVIDER_MAP.keys())}"
        )
    return PROVIDER_MAP[provider_type](config)
```

---

## 6. File Structure

```
scripts/providers/
  llm_providers.py          # renamed from hosted_llm_provider.py
                           # model_rank_candidates() updated to accept ModelProvider
  model_providers/
    __init__.py              # PROVIDER_MAP, make_provider, public exports
    base.py                  # ModelProvider ABC
    claude.py                # ClaudeProvider
    minimax.py               # MiniMaxProvider
    openai_compatible.py     # OpenAICompatibleProvider
```

`llm_providers.py` (renamed from `hosted_llm_provider.py`) contains `model_rank_candidates`, updated to accept a `ModelProvider` instance and call `provider.generate()` instead of subprocess calls.

---

## 7. Migration

1. Create `scripts/providers/model_providers/` with the class hierarchy above.
2. Add `anthropic` and `openai` to `requirements.txt` if not already present.
3. Refactor `model_rank_candidates` in `llm_providers.py` to accept a `ModelProvider` instance and call `generate()`.
4. Refactor content_stage's `claude -p` calls to use `make_provider` + provider instance.
5. Rename `hosted_llm_provider.py` → `llm_providers.py`.
6. Add `providers` section to `config/children/sophie.yaml`.
7. The CLI flags `--content-provider` and `--ranker` remain as-is; they now select the config-driven provider chain.
8. Existing pipeline tests continue to pass as black-box tests.

---

## 8. Error Handling

| Scenario | Behavior |
|---|---|
| Unknown provider name | `ValueError` at startup |
| Required `model` missing | `ValueError` at startup |
| SDK timeout | Ranker: fall back to filtered ordering. Synthesis: propagate. |
| SDK parse error | Ranker: fall back to filtered ordering. Synthesis: propagate. |
| SDK non-success response | Ranker: fall back to filtered ordering. Synthesis: propagate. |

---

## 9. Testing Strategy

- Unit test each provider in isolation (mock SDK client calls).
- Integration test `make_provider` with valid and invalid config.
- Ranking stage and content stage remain black-box tested via existing pipeline tests.
- No new integration tests required at this layer — the existing `test_pipeline_integration.py` covers end-to-end behavior.