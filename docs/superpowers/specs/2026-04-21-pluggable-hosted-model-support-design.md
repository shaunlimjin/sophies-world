# Pluggable Hosted Model Support — Design

## Status

Approved (revised per architectural feedback 2026-04-21).

## Goal

Refactor `hosted_llm_provider.py` so the model (Claude Sonnet vs Opus, future alternatives) can be configured per-child and per-task (synthesis vs. ranking) without code changes.

## Architecture Overview

```
ModelProvider (ABC)
├── ClaudeProvider            → CLI subprocess (no SDK), supports model override via --model flag
└── OpenAICompatibleProvider  → openai Python SDK, supports model override via API payload
                                 (covers Ollama, LM Studio, MiniMax, and any /v1/chat/completions server)
```

MiniMax is dropped as a dedicated provider — it exposes an OpenAI-compatible endpoint and is configured via `OpenAICompatibleProvider` with `base_url` and `api_key`.

Each provider is a thin, self-contained class implementing `generate(prompt: str, **kwargs) -> dict`. Pipeline stages own task-specific prompt construction and output parsing. The provider handles only the mechanics of invoking the model.

---

## 1. Provider Interface

```python
from abc import ABC, abstractmethod

class ModelProvider(ABC):
    """Base class for all model providers."""

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
        """
```

`generate()` is generic and task-agnostic. It returns `{"result": "...", ...}` — the raw output that the calling stage then interprets. This decouples the provider from pipeline semantics.

---

## 2. Concrete Providers

### ClaudeProvider

Uses the `claude -p` CLI subprocess (no SDK — avoids API billing). Implements custom retry with exponential backoff.

```python
import subprocess
import time

class ClaudeProvider(ModelProvider):
    name = "claude"

    def __init__(self, config: dict):
        self.model = config.get("model")
        if not self.model:
            raise ValueError("ClaudeProvider requires 'model' in config (e.g. 'sonnet', 'opus')")

    def generate(self, prompt: str, **kwargs) -> dict:
        timeout = kwargs.get("timeout", 120)
        max_retries = kwargs.get("max_retries", 2)
        base_delay = kwargs.get("base_delay", 2.0)  # seconds

        for attempt in range(max_retries + 1):
            try:
                result = subprocess.run(
                    ["claude", "-p", prompt,
                     "--output-format", "json",
                     "--model", self.model,
                     "--max-turns", "2"],
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
                return {"result": outer.get("result", "")}
            except json.JSONDecodeError:
                if attempt < max_retries:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                return {"result": "", "error": "parse_error"}

        return {"result": ""}
```

Retry loop uses exponential backoff: delay doubles on each retry (2s → 4s). Catches timeout, non-zero exit, and JSON parse failures. The caller decides how to handle an errored result.

### OpenAICompatibleProvider

Uses the official `openai` Python SDK. Connects to any server implementing the standard `/v1/chat/completions` endpoint (Ollama, LM Studio, MiniMax, etc.).

```python
from openai import OpenAI

class OpenAICompatibleProvider(ModelProvider):
    name = "openai_compatible"

    def __init__(self, config: dict):
        base_url = config.get("base_url", "http://localhost:1234/v1")
        api_key = config.get("api_key", "not-needed")  # most local servers don't require a key
        self.model = config.get("model")
        if not self.model:
            raise ValueError("OpenAICompatibleProvider requires 'model' in config")
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

SDK handles retries, connection pooling, and JSON parsing natively.

---

## 3. Config Structure

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

  # MiniMax example (OpenAI-compatible endpoint):
  # synthesis:
  #   provider: openai_compatible
  #   base_url: https://api.minimax.chat/v1
  #   api_key: YOUR_MINIMAX_API_KEY
  #   model: MiniMax-Text-01
```

The `type` key is removed — routing is done solely on the `provider` name.

If `model` is required by a provider but not provided, `ValueError` is raised at startup.

---

## 4. Provider Factory

```python
PROVIDER_MAP = {
    "claude": ClaudeProvider,
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

## 5. File Structure

```
scripts/providers/
  llm_providers.py            # renamed from hosted_llm_provider.py
                               # model_rank_candidates() updated to accept ModelProvider
  model_providers/
    __init__.py                # PROVIDER_MAP, make_provider, public exports
    base.py                    # ModelProvider ABC
    claude.py                  # ClaudeProvider (CLI subprocess, exponential backoff)
    openai_compatible.py       # OpenAICompatibleProvider (openai SDK)
```

`llm_providers.py` (renamed from `hosted_llm_provider.py`) contains `model_rank_candidates`, updated to accept a `ModelProvider` instance and call `provider.generate()` instead of subprocess calls.

---

## 6. Migration

1. Create `scripts/providers/model_providers/` with the class hierarchy above.
2. Add `openai` to `requirements.txt` if not already present. (No new dependency for ClaudeProvider — it uses existing CLI.)
3. Refactor `model_rank_candidates` in `llm_providers.py` to accept a `ModelProvider` instance and call `generate()`.
4. Refactor content_stage's `claude -p` calls to use `make_provider` + provider instance.
5. Rename `hosted_llm_provider.py` → `llm_providers.py`.
6. Add `providers` section to `config/children/sophie.yaml`.
7. The CLI flags `--content-provider` and `--ranker` remain as-is; they now select the config-driven provider chain.
8. Existing pipeline tests continue to pass as black-box tests.

---

## 7. Error Handling

| Scenario | Behavior |
|---|---|
| Unknown provider name | `ValueError` at startup |
| Required `model` missing | `ValueError` at startup |
| CLI timeout | Ranker: fall back to filtered ordering. Synthesis: propagate. |
| CLI non-zero exit | Ranker: fall back to filtered ordering. Synthesis: propagate. |
| CLI parse error | Ranker: fall back to filtered ordering. Synthesis: propagate. |
| SDK timeout / error | Ranker: fall back to filtered ordering. Synthesis: propagate. |

All error responses from `generate()` include an `"error"` key so callers can distinguish clean results from failures without exceptions.

---

## 8. Testing Strategy

- Unit test each provider in isolation (mock `subprocess.run` for ClaudeProvider; mock `openai.OpenAI` for OpenAICompatibleProvider).
- Integration test `make_provider` with valid and invalid config.
- Ranking stage and content stage remain black-box tested via existing pipeline tests.
- No new integration tests required at this layer — the existing `test_pipeline_integration.py` covers end-to-end behavior.