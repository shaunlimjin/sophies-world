# Pluggable Hosted Model Support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `hosted_llm_provider.py` → `llm_providers.py` and introduce a `ModelProvider` abstraction so models can be configured per-child and per-task (synthesis vs. ranking) via YAML, without code changes.

**Architecture:** A `ModelProvider` ABC with two implementations: `ClaudeProvider` (CLI subprocess with exponential backoff) and `OpenAICompatibleProvider` (openai SDK, covers Ollama, LM Studio, MiniMax). A `make_provider(config)` factory instantiates providers from YAML config. Pipeline stages call `provider.generate(prompt, **kwargs)` — no direct subprocess or SDK calls in stage code.

**Tech Stack:** Python 3, subprocess + time (CLI), openai Python SDK, PyYAML (existing)

---

## File Structure

```
scripts/providers/
  llm_providers.py                      # renamed from hosted_llm_provider.py
                                          # model_rank_candidates() accepts ModelProvider
  model_providers/
    __init__.py                          # PROVIDER_MAP, make_provider, public exports
    base.py                              # ModelProvider ABC
    claude.py                            # ClaudeProvider
    openai_compatible.py                 # OpenAICompatibleProvider
```

**Modified:**
- `config/children/sophie.yaml` — add `providers` section
- `scripts/content_stage.py` — `run_content_provider()` and `run_packet_synthesis_provider()` accept `ModelProvider` instead of calling subprocess directly
- `scripts/ranking_stage.py` — `rank_candidates()` instantiates provider via `make_provider` from config

---

## Dependencies

Add to `requirements.txt`:
```
openai>=1.0.0
```

---

## Task 1: Add openai to requirements.txt

**Files:**
- Modify: `requirements.txt:1`

- [ ] **Step 1: Add openai to requirements.txt**

```
PyYAML>=6.0
openai>=1.0.0
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt && git commit -m "deps: add openai for OpenAICompatibleProvider

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: Create ModelProvider ABC

**Files:**
- Create: `scripts/providers/model_providers/base.py`

- [ ] **Step 1: Write the failing test**

Create `tests/providers/test_model_providers.py`:

```python
from scripts.providers.model_providers.base import ModelProvider

def test_model_provider_is_abc():
    try:
        provider = ModelProvider()
        raise AssertionError("ModelProvider cannot be instantiated directly")
    except TypeError:
        pass  # ABC raises TypeError

def test_model_provider_name_property():
    """Subclasses must implement the name property."""
    class DummyProvider(ModelProvider):
        @property
        def name(self):
            return "dummy"

    p = DummyProvider({})
    assert p.name == "dummy"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/providers/test_model_providers.py::test_model_provider_is_abc tests/providers/test_model_providers.py::test_model_provider_name_property -v
```
Expected: FAIL — no base.py yet

- [ ] **Step 3: Create the directory and base.py**

```bash
mkdir -p scripts/providers/model_providers tests/providers
```

```python
"""ModelProvider ABC and interfaces."""

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

        Recognized kwargs:
        - timeout (int): seconds before timeout (default 120)
        - max_retries (int): number of retry attempts on failure (default 2)
        - base_delay (float): initial backoff delay in seconds (default 2.0, CLI only)
        - debug_dir (Path): directory to write debug artifacts (CLI only)
        - max_turns (int): max turns for CLI (default varies by caller; Mode A uses 10)
        - allowed_tools (str): comma-separated tool names for CLI (e.g. "WebSearch,WebFetch"; Mode A only)

        On error, result dict includes an "error" key describing the failure, e.g.
        {"result": "", "error": "timeout"} or {"result": "", "error": "exit 1"}.

        Note: OpenAICompatibleProvider does not support tools or max_turns. Mode A
        (integrated search) requires a tool-capable provider (only ClaudeProvider currently)."
        """
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/providers/test_model_providers.py::test_model_provider_is_abc tests/providers/test_model_providers.py::test_model_provider_name_property -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/providers/model_providers/base.py tests/providers/test_model_providers.py && git commit -m "feat: add ModelProvider ABC

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: Create ClaudeProvider

**Files:**
- Create: `scripts/providers/model_providers/claude.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/providers/test_model_providers.py`:

```python
import subprocess
from unittest.mock import MagicMock, patch
from scripts.providers.model_providers.claude import ClaudeProvider

def test_claude_provider_requires_model():
    try:
        ClaudeProvider({})
        raise AssertionError("Expected ValueError for missing model")
    except ValueError as exc:
        assert "model" in str(exc).lower()

def test_claude_provider_name():
    provider = ClaudeProvider({"model": "sonnet"})
    assert provider.name == "claude"

def test_claude_provider_generate_success():
    provider = ClaudeProvider({"model": "sonnet"})
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"result": "test output"}'
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = provider.generate("test prompt")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "--model" in args
        assert "sonnet" in args
        assert result["result"] == "test output"

def test_claude_provider_generate_with_tools_and_max_turns():
    """Mode A calls generate with allowed_tools and max_turns=10."""
    provider = ClaudeProvider({"model": "sonnet"})
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"result": "web search output"}'
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = provider.generate(
            "search prompt",
            allowed_tools="WebSearch,WebFetch",
            max_turns=10,
        )
        args = mock_run.call_args[0][0]
        assert "--allowedTools" in args
        assert "WebSearch,WebFetch" in args
        idx = args.index("--max-turns")
        assert args[idx + 1] == "10"
        assert result["result"] == "web search output"

def test_claude_provider_generate_retry_on_nonzero_exit():
    provider = ClaudeProvider({"model": "sonnet"})
    mock_fail = MagicMock()
    mock_fail.returncode = 1
    mock_fail.stdout = ""
    mock_fail.stderr = "rate limit"

    mock_success = MagicMock()
    mock_success.returncode = 0
    mock_success.stdout = '{"result": "recovered"}'
    mock_success.stderr = ""

    with patch("subprocess.run", side_effect=[mock_fail, mock_success]):
        with patch("time.sleep"):
            result = provider.generate("test prompt", max_retries=1, base_delay=0.01)
            assert result["result"] == "recovered"

def test_claude_provider_generate_error_on_exhausted_retries():
    provider = ClaudeProvider({"model": "sonnet"})
    mock_fail = MagicMock()
    mock_fail.returncode = 1
    mock_fail.stdout = ""
    mock_fail.stderr = ""

    with patch("subprocess.run", return_value=mock_fail):
        with patch("time.sleep"):
            result = provider.generate("test prompt", max_retries=0, base_delay=0.01)
            assert "error" in result
            assert result["result"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/providers/test_model_providers.py -v
```
Expected: FAIL — no claude.py yet

- [ ] **Step 3: Write the implementation**

```python
"""ClaudeProvider: CLI subprocess model provider with exponential backoff."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from .base import ModelProvider


class ClaudeProvider(ModelProvider):
    """Uses the `claude -p` CLI subprocess to avoid API billing.
    Implements custom retry with exponential backoff for transient failures.
    """

    name = "claude"

    def __init__(self, config: dict):
        self.model = config.get("model")
        if not self.model:
            raise ValueError(
                "ClaudeProvider requires 'model' in config (e.g. 'sonnet', 'opus')"
            )
        self._debug_dir: Optional[Path] = None
        if "debug_dir" in config:
            self._debug_dir = Path(config["debug_dir"])
            self._debug_dir.mkdir(parents=True, exist_ok=True)

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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/providers/test_model_providers.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/providers/model_providers/claude.py tests/providers/test_model_providers.py && git commit -m "feat: add ClaudeProvider with CLI subprocess and exponential backoff

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: Create OpenAICompatibleProvider

**Files:**
- Create: `scripts/providers/model_providers/openai_compatible.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/providers/test_model_providers.py`:

```python
from scripts.providers.model_providers.openai_compatible import OpenAICompatibleProvider

def test_openai_compatible_requires_model():
    try:
        OpenAICompatibleProvider({})
        raise AssertionError("Expected ValueError for missing model")
    except ValueError as exc:
        assert "model" in str(exc).lower()

def test_openai_compatible_name():
    provider = OpenAICompatibleProvider({"model": "llama3"})
    assert provider.name == "openai_compatible"

def test_openai_compatible_generate_success():
    provider = OpenAICompatibleProvider({
        "model": "llama3",
        "base_url": "http://localhost:1234/v1",
        "api_key": "test-key",
    })

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="synthesized output"))]

    with patch("openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        result = provider.generate("test prompt")
        assert result["result"] == "synthesized output"
        mock_client.chat.completions.create.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/providers/test_model_providers.py -v
```
Expected: FAIL — no openai_compatible.py yet

- [ ] **Step 3: Write the implementation**

```python
"""OpenAICompatibleProvider: openai SDK client for any /v1/chat/completions server."""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from .base import ModelProvider


class OpenAICompatibleProvider(ModelProvider):
    """Uses the openai Python SDK to call any server implementing /v1/chat/completions.
    Covers Ollama, LM Studio, MiniMax, and any OpenAI-API-compatible endpoint.
    """

    name = "openai_compatible"

    def __init__(self, config: dict):
        base_url = config.get("base_url", "http://localhost:1234/v1")
        api_key = config.get("api_key", "not-needed")
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

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/providers/test_model_providers.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/providers/model_providers/openai_compatible.py tests/providers/test_model_providers.py && git commit -m "feat: add OpenAICompatibleProvider using openai SDK

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: Create model_providers __init__.py with factory

**Files:**
- Create: `scripts/providers/model_providers/__init__.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/providers/test_model_providers.py`:

```python
from scripts.providers.model_providers import make_provider, PROVIDER_MAP

def test_make_provider_unknown_raises():
    try:
        make_provider({"provider": "nonexistent"})
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "nonexistent" in str(exc)

def test_make_provider_missing_provider_key():
    try:
        make_provider({})
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "provider" in str(exc)

def test_make_provider_claude():
    provider = make_provider({"provider": "claude", "model": "sonnet"})
    assert provider.name == "claude"

def test_make_provider_openai_compatible():
    provider = make_provider({
        "provider": "openai_compatible",
        "model": "llama3",
        "base_url": "http://localhost:1234/v1",
    })
    assert provider.name == "openai_compatible"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/providers/test_model_providers.py -v
```
Expected: FAIL — no __init__.py yet

- [ ] **Step 3: Write __init__.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/providers/test_model_providers.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/providers/model_providers/__init__.py tests/providers/test_model_providers.py && git commit -m "feat: add model_providers factory with make_provider

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: Rename hosted_llm_provider.py → llm_providers.py and refactor

**Files:**
- Rename: `scripts/providers/hosted_llm_provider.py` → `scripts/providers/llm_providers.py`
- Modify: `scripts/ranking_stage.py:76-77`

- [ ] **Step 1: Rename the file**

```bash
git mv scripts/providers/hosted_llm_provider.py scripts/providers/llm_providers.py
```

- [ ] **Step 2: Update import in ranking_stage.py**

Change:
```python
from providers.hosted_llm_provider import model_rank_candidates
```
To:
```python
from providers.llm_providers import model_rank_candidates
```

- [ ] **Step 3: Commit rename**

```bash
git add scripts/ranking_stage.py && git mv scripts/providers/hosted_llm_provider.py scripts/providers/llm_providers.py && git commit -m "refactor: rename hosted_llm_provider.py -> llm_providers.py

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: Update model_rank_candidates in llm_providers.py to accept ModelProvider

**Files:**
- Modify: `scripts/providers/llm_providers.py`

- [ ] **Step 1: Add test for model_rank_candidates with provider**

Create `tests/providers/test_llm_providers.py`:

```python
from unittest.mock import MagicMock
from scripts.providers.llm_providers import model_rank_candidates

def test_model_rank_candidates_accepts_provider():
    mock_provider = MagicMock()
    mock_provider.generate.return_value = {
        "result": '[{"index": 0, "title": "Test", "reasons": ["test"]}]'
    }

    pool = {
        "sections": [
            {
                "section_id": "weird_but_true",
                "filtered_candidates": [
                    {"title": "Test", "url": "http://example.com", "domain": "example.com", "snippet": "Test snippet"}
                ]
            }
        ],
        "recent_headlines": []
    }
    config = {
        "profile": {"name": "Sophie", "age_band": "4th-grade", "interests": {"active": []}},
        "research": {"ranking": {"sections": {"weird_but_true": {"max_ranked": 3}}}}
    }

    result = model_rank_candidates(pool, config, provider=mock_provider)
    mock_provider.generate.assert_called_once()
    assert "sections" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/providers/test_llm_providers.py -v
```
Expected: FAIL — model_rank_candidates doesn't accept `provider` kwarg yet

- [ ] **Step 3: Refactor model_rank_candidates to accept and use ModelProvider**

Read the current `model_rank_candidates` and `_run_model_ranker`. Replace the subprocess call inside `_run_model_ranker` with `provider.generate()`:

The new signature:
```python
def model_rank_candidates(
    filtered_pool: Dict[str, Any],
    config: dict,
    repo_root: Path,
    provider: ModelProvider = None,  # NEW kwarg
    timeout_seconds: int = 120,
    max_retries: int = 2,
) -> Dict[str, Any]:
```

Inside `_run_model_ranker`, replace the `subprocess.run` block with:
```python
result = provider.generate(
    prompt,
    timeout=timeout_seconds,
    max_retries=max_retries,
    debug_dir=debug_dir,
)
```

Also update the fallback to check for `result.get("error")` and fall back to filtered ordering when error is present. Also write the prompt and stdout to debug files.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/providers/test_llm_providers.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/providers/llm_providers.py tests/providers/test_llm_providers.py && git commit -m "refactor: model_rank_candidates accepts ModelProvider kwarg

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: Wire provider into ranking_stage rank_candidates

**Files:**
- Modify: `scripts/ranking_stage.py:66-78`

- [ ] **Step 1: Write the test**

In `tests/providers/test_llm_providers.py`, add:

```python
def test_rank_candidates_wires_provider_from_config():
    """rank_candidates passes make_provider result to model_rank_candidates."""
    from scripts.providers.model_providers import make_provider

    mock_provider = MagicMock()
    mock_provider.generate.return_value = {
        "result": '[{"index": 0, "title": "Test", "reasons": ["test"]}]'
    }

    with patch("scripts.ranking_stage.make_provider", return_value=mock_provider):
        pool = {
            "sections": [{
                "section_id": "weird_but_true",
                "filtered_candidates": [{"title": "Test", "url": "http://example.com", "domain": "example.com", "snippet": "Test"}]
            }],
            "recent_headlines": []
        }
        config = {
            "profile": {
                "name": "Sophie",
                "age_band": "4th-grade",
                "interests": {"active": []},
                "providers": {
                    "ranking": {"provider": "claude", "model": "sonnet"}
                }
            },
            "research": {
                "ranking": {
                    "sections": {"weird_but_true": {"max_ranked": 3}}
                }
            }
        }
        # Call rank_candidates with hosted_model_ranker
        from scripts.ranking_stage import rank_candidates
        result = rank_candidates(pool, config, "hosted_model_ranker", Path("/tmp"))
        assert mock_provider.generate.called
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/providers/test_llm_providers.py::test_rank_candidates_wires_provider_from_config -v
```
Expected: FAIL — rank_candidates doesn't wire provider yet

- [ ] **Step 3: Update rank_candidates to use make_provider**

Update `rank_candidates` in `ranking_stage.py`:

```python
def rank_candidates(
    filtered_pool: Dict[str, Any],
    config: dict,
    ranker_provider: str,
    repo_root: Path,
) -> Dict[str, Any]:
    if ranker_provider == "heuristic_ranker":
        return _heuristic_rank(filtered_pool, config, repo_root)
    if ranker_provider == "hosted_model_ranker":
        from providers.model_providers import make_provider
        generation_cfg = config.get("profile", {}).get("newsletter", {}).get("generation", {})
        provider_cfg = generation_cfg.get("providers", {}).get("ranking")
        if not provider_cfg:
            raise ValueError(
                "hosted_model_ranker requires 'providers.ranking' in config. "
                "Example:\n  providers:\n    ranking:\n      provider: claude\n      model: sonnet"
            )
        provider = make_provider(provider_cfg)
        from providers.llm_providers import model_rank_candidates
        return model_rank_candidates(filtered_pool, config, repo_root, provider=provider)
    raise ValueError(f"Unknown ranker_provider: '{ranker_provider}'")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/providers/test_llm_providers.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/ranking_stage.py tests/providers/test_llm_providers.py && git commit -m "feat: wire make_provider into rank_candidates for hosted_model_ranker

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 9: Update content_stage to use ModelProvider

**Files:**
- Modify: `scripts/content_stage.py`

The two functions to update are `run_content_provider()` (line 202) and `run_packet_synthesis_provider()` (line 402). Both call `subprocess.run(["claude", "-p", ...])` directly.

- [ ] **Step 1: Write tests for content_stage provider injection**

```python
from unittest.mock import MagicMock
from scripts.content_stage import run_content_provider, run_packet_synthesis_provider

def test_run_content_provider_uses_provider(monkeypatch):
    mock_provider = MagicMock()
    mock_provider.generate.return_value = {"result": '{"test": true}'}

    # Mock parse_content_output to avoid JSON dependency
    monkeypatch.setattr("scripts.content_stage.parse_content_output", lambda raw, repo: {"test": True})

    result = run_content_provider("prompt", Path("/tmp"), provider=mock_provider)
    mock_provider.generate.assert_called_once()
    args, kwargs = mock_provider.generate.call_args
    assert "prompt" in args[0] or kwargs.get("prompt") == "prompt"

def test_run_packet_synthesis_provider_uses_provider(monkeypatch):
    mock_provider = MagicMock()
    mock_provider.generate.return_value = {"result": '{"test": true}'}

    with patch("scripts.content_stage.parse_content_output", return_value={"test": True}):
        result = run_packet_synthesis_provider("prompt", Path("/tmp"), provider=mock_provider)
        mock_provider.generate.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_content_stage.py -v
```
Expected: FAIL — content_stage doesn't accept `provider` kwarg yet

- [ ] **Step 3: Refactor run_content_provider and run_packet_synthesis_provider**

Both functions take `provider=None` as a kwarg. When provider is None (backward compat), they fall back to the existing subprocess behavior. When provider is provided, they call `provider.generate()`.

```python
def run_content_provider(prompt: str, repo_root: Path, timeout_seconds: int = 300, provider=None, **kwargs) -> str:
    debug_dir = get_debug_dir(repo_root)
    (debug_dir / "last-content-prompt.txt").write_text(prompt, encoding="utf-8")

    if provider is not None:
        result = provider.generate(
            prompt,
            timeout=timeout_seconds,
            max_retries=2,
            debug_dir=debug_dir,
            **kwargs,
        )
        raw_output = result.get("result", "")
        if "error" in result:
            print(f"content provider error: {result['error']}", file=sys.stderr)
        (debug_dir / "last-content-stdout.txt").write_text(raw_output, encoding="utf-8")
        if not raw_output:
            sys.exit(1)
        return raw_output

    # Existing subprocess path (backward compat) — hardcodes Mode A tools
    try:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--allowedTools", "WebSearch,WebFetch",
                "--output-format", "json",
                "--max-turns", "10",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"content provider timed out after {timeout_seconds}s") from exc
    (debug_dir / "last-content-stdout.txt").write_text(result.stdout or "", encoding="utf-8")
    (debug_dir / "last-content-stderr.txt").write_text(result.stderr or "", encoding="utf-8")
    if result.returncode != 0:
        print(f"claude exited with code {result.returncode}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout
```

Similarly for `run_packet_synthesis_provider` — add `provider=None, **kwargs`, use provider.generate() with **kwargs when available, fall back to subprocess otherwise.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_content_stage.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/content_stage.py tests/test_content_stage.py && git commit -m "refactor: run_content_provider and run_packet_synthesis_provider accept optional ModelProvider

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 10: Wire provider into generate.py for Mode B

**Files:**
- Modify: `scripts/generate.py`

`run_mode_b()` at line 150 calls `run_packet_synthesis_provider(prompt, repo_root)`. It needs to instantiate a provider from config and pass it in.

- [ ] **Step 1: Write test for provider wiring in generate.py**

```python
from unittest.mock import MagicMock, patch
from scripts.generate import run_mode_b

def test_run_mode_b_wires_provider():
    mock_provider = MagicMock()
    mock_provider.generate.return_value = {
        "result": '{"greeting_text": "Hi Sophie", "sections": []}'
    }

    config = {
        "profile": {
            "id": "sophie",
            "name": "Sophie",
            "age_band": "4th-grade",
            "newsletter": {
                "generation": {
                    "providers": {
                        "synthesis": {"provider": "claude", "model": "opus"}
                    }
                }
            },
            "interests": {"active": []},
        },
        "sections": {},
        "research": {"ranking": {"sections": {}}},
        "theme": "default",
    }

    with patch("scripts.generate.run_packet_synthesis_provider", return_value='{"greeting_text": "Hi", "sections": []}'):
        with patch("scripts.generate.parse_content_output", return_value={"greeting_text": "Hi", "sections": []}):
            with patch("scripts.generate.validate_issue_artifact"):
                with patch("scripts.ranking_stage.prefilter_candidates", return_value={"sections": []}):
                    with patch("scripts.ranking_stage.rank_candidates", return_value={"sections": []}):
                        result = run_mode_b(
                            date=date.today(),
                            issue_num=1,
                            config=config,
                            recent_headlines=[],
                            repo_root=Path("/tmp"),
                            ranker_provider="heuristic_ranker",
                            refresh_research=True,
                        )
                        # Verify provider was passed
                        # (Full integration test — mock the whole synthesis path)
```

- [ ] **Step 2: Run test to verify it fails**

The test above is more of an integration test. Run it to confirm the current code doesn't wire provider.

```bash
pytest tests/test_generate.py -v
```

- [ ] **Step 3: Update run_mode_b to pass provider to run_packet_synthesis_provider**

In `generate.py`, at the top of `run_mode_b`, add provider instantiation:

```python
def run_mode_b(...):
    from providers.model_providers import make_provider
    generation_cfg = config["profile"].get("newsletter", {}).get("generation", {})
    synthesis_provider_cfg = generation_cfg.get("providers", {}).get("synthesis")
    synthesis_provider = make_provider(synthesis_provider_cfg) if synthesis_provider_cfg else None

    # ... existing code ...

    # In the packet synthesis call, pass provider:
    raw_output = run_packet_synthesis_provider(prompt, repo_root, provider=synthesis_provider)
```

Also update `run_mode_a` similarly. Since Mode A requires web tools (WebSearch, WebFetch), it passes them explicitly when calling the provider:

```python
def run_mode_a(today, issue_num, config, recent_headlines, repo_root):
    from providers.model_providers import make_provider
    generation_cfg = config["profile"].get("newsletter", {}).get("generation", {})
    synthesis_provider_cfg = generation_cfg.get("providers", {}).get("synthesis")
    synthesis_provider = make_provider(synthesis_provider_cfg) if synthesis_provider_cfg else None

    prompt = build_content_prompt(today, issue_num, config, recent_headlines)

    if synthesis_provider is not None:
        raw_output = run_content_provider(
            prompt, repo_root,
            provider=synthesis_provider,
            allowed_tools="WebSearch,WebFetch",
            max_turns=10,
        )
    else:
        raw_output = run_content_provider(prompt, repo_root)

    issue = parse_content_output(raw_output, repo_root)
    validate_issue_artifact(issue)
    return issue
```

- [ ] **Step 4: Run existing tests to verify nothing is broken**

```bash
pytest tests/test_generate.py tests/test_pipeline_integration.py -v
```
Expected: PASS (backward compat — existing subprocess path is still used when provider is None)

- [ ] **Step 5: Commit**

```bash
git add scripts/generate.py tests/test_generate.py && git commit -m "feat: wire ModelProvider into generate.py run_mode_a and run_mode_b

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 11: Update sophie.yaml with providers section

**Files:**
- Modify: `config/children/sophie.yaml`

Add `providers` section under `newsletter.generation`:

```yaml
providers:
  synthesis:
    provider: claude
    model: opus
  ranking:
    provider: claude
    model: sonnet
```

- [ ] **Step 1: Add providers section**

```yaml
generation:
  research_provider: brave_deterministic
  ranker_provider: heuristic_ranker
  content_provider: hosted_integrated_search
  render_provider: local_renderer
  fallback_content_provider: hosted_integrated_search
  providers:
    synthesis:
      provider: claude
      model: opus
    ranking:
      provider: claude
      model: sonnet
```

- [ ] **Step 2: Commit**

```bash
git add config/children/sophie.yaml && git commit -m "feat: add providers section to sophie.yaml for pluggable model support

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 12: Smoke test — run the full pipeline

- [ ] **Step 1: Run generate.py in test mode**

```bash
python3 scripts/generate.py --test
```

Expected: completes without errors, produces HTML output. Provider is instantiated from config and used.

- [ ] **Step 2: Commit final changes**

---

## Spec Coverage Checklist

| Spec Section | Task |
|---|---|
| Provider Interface (generate) | Tasks 2, 3, 4, 5 |
| ClaudeProvider (CLI, exponential backoff) | Task 3 |
| OpenAICompatibleProvider (SDK) | Task 4 |
| Config structure (providers section) | Task 11 |
| Provider factory (make_provider) | Task 5 |
| File rename hosted_llm_provider.py → llm_providers.py | Task 6 |
| model_rank_candidates accepts ModelProvider | Task 7 |
| content_stage uses provider | Task 9 |
| ranking_stage wires provider from config | Task 8 |
| generate.py wires provider | Task 10 |
| openai in requirements.txt | Task 1 |