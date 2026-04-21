# Pluggable Hosted Model Support — Design

## Status

Approved.

## Goal

Refactor `hosted_llm_provider.py` so the model (Claude Sonnet vs Opus, MiniMax, future alternatives) can be configured per-child and per-task (synthesis vs. ranking) without code changes.

## Architecture Overview

```
ModelProvider (ABC)
├── HostedProvider (ABC)
│   ├── ClaudeProvider     → supports --model flag
│   ├── MiniMaxProvider    → no model param
│   └── OpenAIProvider     → supports --model flag (future)
└── LocalProvider (ABC)    → no model param (e.g. Ollama)
```

Each provider is a thin, self-contained class that knows how to invoke its underlying CLI or API. The config layer only names the provider and model; the provider handles the mechanics.

---

## 1. Provider Interface

```python
from abc import ABC, abstractmethod

class ModelProvider(ABC):
    """Base class for all model providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier, e.g. 'claude', 'minimax', 'ollama'."""

    @abstractmethod
    def rank(self, prompt: str, **kwargs) -> dict:
        """Run ranking task. Returns dict with 'result' key (JSON string)."""

    @abstractmethod
    def synthesize(self, prompt: str, **kwargs) -> dict:
        """Run synthesis task. Returns dict with 'result' key (JSON string)."""
```

Both `rank` and `synthesize` return `{"result": "...", ...}`. The caller (ranking_stage, content_stage) doesn't care which CLI or API produced it.

---

## 2. HostedProvider Base

```python
class HostedProvider(ModelProvider, ABC):
    """Base for cloud-hosted model providers."""

    @property
    @abstractmethod
    def supports_model_param(self) -> bool:
        """Whether this provider accepts a model override."""

    def build_cli_args(self, prompt: str, model: str | None = None) -> list[str]:
        """Build the CLI invocation args. Override for providers with custom flag styles."""
        args = [self.name, "-p", prompt, "--output-format", "json"]
        if model and self.supports_model_param:
            args.extend(["--model", model])
        return args
```

`supports_model_param` gates whether the model arg gets passed. Providers that need a different flag style (e.g. `--model` vs `-m`) override `build_cli_args`.

---

## 3. Concrete Providers

### ClaudeProvider

```python
class ClaudeProvider(HostedProvider):
    name = "claude"
    supports_model_param = True

    def rank(self, prompt: str, model: str | None = None, timeout: int = 120, **kwargs) -> dict:
        args = self.build_cli_args(prompt, model)
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return self._parse_output(result, prompt, kwargs.get("debug_dir"))

    def synthesize(self, prompt: str, model: str | None = None, timeout: int = 120, **kwargs) -> dict:
        args = self.build_cli_args(prompt, model)
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return self._parse_output(result, prompt, kwargs.get("debug_dir"))

    def _parse_output(self, result, prompt, debug_dir) -> dict:
        # handles exit code checking, stdout/stderr logging, JSON parsing
        ...
```

### MiniMaxProvider

```python
class MiniMaxProvider(HostedProvider):
    name = "minimax"
    supports_model_param = False
    # inherits build_cli_args — model arg silently ignored
```

### LocalProvider

```python
class LocalProvider(ModelProvider, ABC):
    """For local servers (e.g. Ollama). Uses HTTP client instead of subprocess."""

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL of the running local model server."""

    def rank(self, prompt: str, **kwargs) -> dict:
        # POST to /v1/generate or similar
        response = requests.post(f"{self.base_url}/v1/generate", json={"prompt": prompt})
        return {"result": response.json()["response"]}
```

---

## 4. Config Structure

In `config/children/sophie.yaml`:

```yaml
providers:
  synthesis:
    type: hosted
    provider: claude
    model: opus
  ranking:
    type: hosted
    provider: claude
    model: sonnet

  # Future local example:
  # synthesis:
  #   type: local
  #   provider: ollama
  #   model: llama3
```

If `model` is provided for a provider where `supports_model_param` is `False`, it is silently ignored (LocalProvider, MiniMaxProvider). If a provider requires a model and none is provided, raise `ValueError` at startup.

---

## 5. Provider Factory

```python
PROVIDER_MAP = {
    "claude": ClaudeProvider,
    "minimax": MiniMaxProvider,
    "ollama": OllamaProvider,
}

def make_provider(config: dict) -> ModelProvider:
    provider_type = config["provider"]
    if provider_type not in PROVIDER_MAP:
        raise ValueError(
            f"Unknown provider '{provider_type}'. "
            f"Available: {list(PROVIDER_MAP.keys())}"
        )
    return PROVIDER_MAP[provider_type](config)
```

Called once per task (synthesis, ranking) at pipeline startup. The provider instance is passed into the stage that needs it.

---

## 6. File Structure

```
scripts/providers/
  model_providers/
    __init__.py          # PROVIDER_MAP, make_provider, public exports
    base.py              # ModelProvider, HostedProvider, LocalProvider ABCs
    claude.py            # ClaudeProvider
    minimax.py           # MiniMaxProvider
    local.py             # LocalProvider (Ollama)
```

`hosted_llm_provider.py` remains as the module containing `model_rank_candidates`, which gets updated to accept a `ModelProvider` instance rather than calling subprocess directly.

---

## 7. Migration

1. Create `scripts/providers/model_providers/` with the class hierarchy above.
2. Refactor `model_rank_candidates` in `hosted_llm_provider.py` to accept a `ModelProvider` instance.
3. Refactor content_stage's `claude -p` calls to use `make_provider` + provider instance.
4. Add `providers` section to `config/children/sophie.yaml`.
5. The CLI flags `--content-provider` and `--ranker` remain as-is; they now select the config-driven provider chain.
6. Existing pipeline tests continue to pass as black-box tests.

---

## 8. Error Handling

| Scenario | Behavior |
|---|---|
| Unknown provider name | `ValueError` at startup |
| Model param on unsupported provider | Silently ignored |
| Required model param missing | `ValueError` at startup |
| Subprocess timeout | Ranking: fall back to filtered ordering. Synthesis: propagate. |
| Parse error | Ranking: fall back to filtered ordering. Synthesis: propagate. |
| Non-zero exit code | Log stderr, treat as failure with appropriate fallback |

---

## 9. Testing Strategy

- Unit test each provider in isolation (mock `subprocess.run` / `requests.post`).
- Integration test `make_provider` with valid and invalid config.
- Ranking stage and content stage remain black-box tested via existing pipeline tests.
- No new integration tests required at this layer — the existing `test_pipeline_integration.py` covers end-to-end behavior.