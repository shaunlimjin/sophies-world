# OpenAI Agentic Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the existing `OpenAIAgenticProvider` skeleton so it fully implements the spec: correct multi-turn message serialization, `system_prompt` support, `query` field in tool results, snippet truncation, per-tool timeout, `max_tool_calls_total`, and stable error vocabulary.

**Architecture:** The skeleton in `openai_agentic.py` is structurally sound — its `__init__`, loop, and tool dispatch all stay. Each task targets one specific gap identified in spec review. No new abstractions beyond extracting `_load_api_key` (shared by two files) and `_run_search` (needed for timeout wrapping). `OpenAICompatibleProvider` is not touched beyond the shared utility import.

**Tech Stack:** Python 3.x, `openai` SDK v1+, `concurrent.futures` (stdlib), `pytest`, `unittest.mock`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `scripts/providers/model_providers/_api_key.py` | **Create** | Shared `load_api_key` util — consolidates duplicate logic from both provider files |
| `scripts/providers/model_providers/openai_compatible.py` | **Modify** | Import `load_api_key` from `_api_key`, remove local `_load_minimax_api_key` |
| `scripts/providers/model_providers/openai_agentic.py` | **Modify** | All spec fixes: serialization, system_prompt, tool result shape, timeout, max_tool_calls_total, error vocab |
| `scripts/providers/model_providers/__init__.py` | **Modify** | Update `make_provider` docstring to mention `openai_agentic` |
| `tests/providers/test_api_key.py` | **Create** | Tests for the shared utility |
| `tests/providers/test_openai_agentic.py` | **Modify** | Add all missing test cases from spec §13.1 |

---

## Task 1: Extract shared `_load_api_key` utility

Two files have near-identical API key loading logic. Consolidate them.

**Files:**
- Create: `scripts/providers/model_providers/_api_key.py`
- Create: `tests/providers/test_api_key.py`
- Modify: `scripts/providers/model_providers/openai_compatible.py`
- Modify: `scripts/providers/model_providers/openai_agentic.py`

- [ ] **Step 1: Write tests for the new utility**

```python
# tests/providers/test_api_key.py
import os
import pytest
from scripts.providers.model_providers._api_key import load_api_key


def test_load_from_env(monkeypatch):
    monkeypatch.setenv("MY_TEST_KEY", "from-env")
    assert load_api_key("MY_TEST_KEY") == "from-env"


def test_load_from_dotenv(tmp_path):
    (tmp_path / ".env").write_text('MY_TEST_KEY=from-dotenv\n', encoding="utf-8")
    assert load_api_key("MY_TEST_KEY", repo_root=tmp_path) == "from-dotenv"


def test_dotenv_strips_quotes(tmp_path):
    (tmp_path / ".env").write_text('MY_TEST_KEY="quoted-value"\n', encoding="utf-8")
    assert load_api_key("MY_TEST_KEY", repo_root=tmp_path) == "quoted-value"


def test_dotenv_takes_priority_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_TEST_KEY", "from-env")
    (tmp_path / ".env").write_text('MY_TEST_KEY=from-dotenv\n', encoding="utf-8")
    assert load_api_key("MY_TEST_KEY", repo_root=tmp_path) == "from-dotenv"


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("NONEXISTENT_KEY_XYZ", raising=False)
    with pytest.raises(RuntimeError, match="NONEXISTENT_KEY_XYZ"):
        load_api_key("NONEXISTENT_KEY_XYZ")
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
cd /Users/hobbes/dev/sophies-world
python -m pytest tests/providers/test_api_key.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` (file doesn't exist yet)

- [ ] **Step 3: Create the utility**

```python
# scripts/providers/model_providers/_api_key.py
"""Shared utility for loading API keys from .env or environment."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def load_api_key(key_name: str, repo_root: Optional[Path] = None) -> str:
    """Load an API key from .env file (if repo_root given) or environment variable."""
    if repo_root:
        env_path = repo_root / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith(f"{key_name}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    key = os.environ.get(key_name, "")
    if not key:
        raise RuntimeError(f"{key_name} not found in .env or environment")
    return key
```

- [ ] **Step 4: Run tests, confirm they pass**

```bash
python -m pytest tests/providers/test_api_key.py -v
```

Expected: 5 passed

- [ ] **Step 5: Update `openai_compatible.py` to use the shared utility**

Replace the module-level `_load_minimax_api_key` function and its call site. Final content of the relevant section:

```python
# scripts/providers/model_providers/openai_compatible.py
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
```

- [ ] **Step 6: Update `openai_agentic.py` to use the shared utility**

Replace the local `_load_api_key` function definition and import with:

```python
from ._api_key import load_api_key
```

Remove the `def _load_api_key(...)` function at the top of the file. Both call sites (`MINIMAX_API_KEY` and `BRAVE_API_KEY`) already use the right signature.

- [ ] **Step 7: Run existing provider tests to confirm no regressions**

```bash
python -m pytest tests/providers/ -v
```

Expected: all existing tests pass

- [ ] **Step 8: Commit**

```bash
git add scripts/providers/model_providers/_api_key.py \
        scripts/providers/model_providers/openai_compatible.py \
        scripts/providers/model_providers/openai_agentic.py \
        tests/providers/test_api_key.py
git commit -m "refactor: extract shared load_api_key utility from provider files"
```

---

## Task 2: Fix assistant message serialization

The OpenAI SDK returns Pydantic objects from `response.choices[0].message`. Appending them to `messages` works for the official endpoint but breaks with third-party servers (like MiniMax) that strictly require plain dicts in subsequent turns.

**Files:**
- Modify: `scripts/providers/model_providers/openai_agentic.py`
- Modify: `tests/providers/test_openai_agentic.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/providers/test_openai_agentic.py`:

```python
def test_assistant_message_is_dict_in_multiturn():
    """Second API call must receive a plain dict for the assistant turn, not an SDK object."""
    provider = OpenAIAgenticProvider({"model": "test-model", "api_key": "test-key"})

    mock_brave = MagicMock()
    mock_brave.search.return_value = [{"title": "T", "url": "U", "snippet": "S"}]
    provider._brave_client = mock_brave

    mock_tc = MagicMock()
    mock_tc.id = "call_abc"
    mock_tc.type = "function"
    mock_tc.function.name = "WebSearch"
    mock_tc.function.arguments = json.dumps({"query": "news"})

    mock_msg1 = MagicMock()
    mock_msg1.content = None
    mock_msg1.tool_calls = [mock_tc]

    mock_msg2 = MagicMock()
    mock_msg2.content = "Answer."
    mock_msg2.tool_calls = None

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=mock_msg1, finish_reason="tool_calls")]),
        MagicMock(choices=[MagicMock(message=mock_msg2, finish_reason="stop")]),
    ]
    provider.client = mock_client

    provider.generate("test prompt", allowed_tools="WebSearch")

    second_call_messages = mock_client.chat.completions.create.call_args_list[1][1]["messages"]
    # [user_dict, assistant_msg, tool_result_dict]
    assistant_msg = second_call_messages[1]
    assert isinstance(assistant_msg, dict), "assistant message must be a plain dict, not an SDK Pydantic object"
    assert assistant_msg["role"] == "assistant"
    assert "tool_calls" in assistant_msg
```

- [ ] **Step 2: Run the test, confirm it fails**

```bash
python -m pytest tests/providers/test_openai_agentic.py::test_assistant_message_is_dict_in_multiturn -v
```

Expected: `AssertionError: assistant message must be a plain dict` (because current code appends the raw MagicMock/Pydantic object)

- [ ] **Step 3: Fix the serialization in `generate()`**

In `openai_agentic.py`, find the `messages.append(message)` line and replace the entire block that appends the assistant turn with:

```python
# Build a plain dict — OpenAI SDK returns Pydantic objects; third-party
# endpoints need plain dicts in subsequent turns.
msg_dict: dict = {"role": "assistant", "content": message.content}
if message.tool_calls:
    msg_dict["tool_calls"] = [
        {
            "id": tc.id,
            "type": tc.type,
            "function": {
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            },
        }
        for tc in message.tool_calls
    ]
messages.append(msg_dict)
```

Remove the old `messages.append(message)` line and the comment that preceded it.

- [ ] **Step 4: Run the test, confirm it passes**

```bash
python -m pytest tests/providers/test_openai_agentic.py -v
```

Expected: all tests pass including the new one

- [ ] **Step 5: Commit**

```bash
git add scripts/providers/model_providers/openai_agentic.py \
        tests/providers/test_openai_agentic.py
git commit -m "fix: serialize assistant messages to dicts for multi-turn compatibility"
```

---

## Task 3: Add `system_prompt` support

The content stage passes editorial context (reading level, tone, section definitions) as a system message. Without this, the provider cannot replicate Mode A behavior.

**Files:**
- Modify: `scripts/providers/model_providers/openai_agentic.py`
- Modify: `tests/providers/test_openai_agentic.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/providers/test_openai_agentic.py`:

```python
def test_system_prompt_prepended_as_first_message():
    provider = OpenAIAgenticProvider({"model": "test-model", "api_key": "test-key"})

    mock_msg = MagicMock()
    mock_msg.content = "newsletter content"
    mock_msg.tool_calls = None

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=mock_msg, finish_reason="stop")]
    )
    provider.client = mock_client

    provider.generate("Write the newsletter.", system_prompt="You are a newsletter writer for children.")

    call_messages = mock_client.chat.completions.create.call_args[1]["messages"]
    assert len(call_messages) == 2
    assert call_messages[0]["role"] == "system"
    assert call_messages[0]["content"] == "You are a newsletter writer for children."
    assert call_messages[1]["role"] == "user"
    assert call_messages[1]["content"] == "Write the newsletter."


def test_no_system_prompt_omits_system_message():
    provider = OpenAIAgenticProvider({"model": "test-model", "api_key": "test-key"})

    mock_msg = MagicMock()
    mock_msg.content = "response"
    mock_msg.tool_calls = None

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=mock_msg, finish_reason="stop")]
    )
    provider.client = mock_client

    provider.generate("prompt")

    call_messages = mock_client.chat.completions.create.call_args[1]["messages"]
    assert len(call_messages) == 1
    assert call_messages[0]["role"] == "user"
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
python -m pytest tests/providers/test_openai_agentic.py::test_system_prompt_prepended_as_first_message tests/providers/test_openai_agentic.py::test_no_system_prompt_omits_system_message -v
```

Expected: `AssertionError` on message count or role checks

- [ ] **Step 3: Implement `system_prompt` kwarg in `generate()`**

In `generate()`, find where `messages` is initialized and replace it:

```python
system_prompt = kwargs.get("system_prompt")

messages: list = []
if system_prompt:
    messages.append({"role": "system", "content": system_prompt})
messages.append({"role": "user", "content": prompt})
```

Also add `system_prompt` to the kwargs block at the top of `generate()` alongside `timeout`, `max_turns`, etc. (just the `kwargs.get` line above — no other change needed).

- [ ] **Step 4: Run the tests, confirm they pass**

```bash
python -m pytest tests/providers/test_openai_agentic.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add scripts/providers/model_providers/openai_agentic.py \
        tests/providers/test_openai_agentic.py
git commit -m "feat: add system_prompt kwarg support to OpenAIAgenticProvider"
```

---

## Task 4: Fix tool result shape — `query` field, snippet truncation, `_run_search` extraction

Three related fixes to `_execute_tool`: (1) the `query` field is missing from success payloads, (2) snippets are not truncated, (3) extract the Brave call into `_run_search` to enable per-tool timeout wrapping in the next task.

**Files:**
- Modify: `scripts/providers/model_providers/openai_agentic.py`
- Modify: `tests/providers/test_openai_agentic.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/providers/test_openai_agentic.py`:

```python
def test_tool_result_includes_query_field():
    provider = OpenAIAgenticProvider({"model": "test-model", "api_key": "test-key"})

    mock_brave = MagicMock()
    mock_brave.search.return_value = [{"title": "T", "url": "U", "snippet": "Some snippet"}]
    provider._brave_client = mock_brave

    mock_tc = MagicMock()
    mock_tc.function.name = "WebSearch"
    mock_tc.function.arguments = json.dumps({"query": "tariff news april 2026"})

    payload = json.loads(provider._execute_tool(mock_tc))

    assert "query" in payload, "result must include 'query' field"
    assert payload["query"] == "tariff news april 2026"
    assert "results" in payload


def test_snippet_truncated_to_300_chars():
    provider = OpenAIAgenticProvider({"model": "test-model", "api_key": "test-key"})

    mock_brave = MagicMock()
    mock_brave.search.return_value = [{"title": "T", "url": "U", "snippet": "x" * 500}]
    provider._brave_client = mock_brave

    mock_tc = MagicMock()
    mock_tc.function.name = "WebSearch"
    mock_tc.function.arguments = json.dumps({"query": "news"})

    payload = json.loads(provider._execute_tool(mock_tc))

    assert len(payload["results"][0]["snippet"]) == 300


def test_empty_search_results_returns_stable_shape():
    provider = OpenAIAgenticProvider({"model": "test-model", "api_key": "test-key"})

    mock_brave = MagicMock()
    mock_brave.search.return_value = []
    provider._brave_client = mock_brave

    mock_tc = MagicMock()
    mock_tc.function.name = "WebSearch"
    mock_tc.function.arguments = json.dumps({"query": "very obscure topic"})

    payload = json.loads(provider._execute_tool(mock_tc))

    assert payload["query"] == "very obscure topic"
    assert payload["results"] == []


def test_malformed_tool_args_returns_invalid_arguments():
    provider = OpenAIAgenticProvider({"model": "test-model", "api_key": "test-key"})

    mock_tc = MagicMock()
    mock_tc.function.name = "WebSearch"
    mock_tc.function.arguments = "not valid json {"

    payload = json.loads(provider._execute_tool(mock_tc))

    assert payload["error"] == "invalid_arguments"


def test_unsupported_tool_name():
    provider = OpenAIAgenticProvider({"model": "test-model", "api_key": "test-key"})

    mock_tc = MagicMock()
    mock_tc.function.name = "RunCode"
    mock_tc.function.arguments = json.dumps({"code": "print('hi')"})

    payload = json.loads(provider._execute_tool(mock_tc))

    assert "unknown_tool" in payload["error"]
    assert "RunCode" in payload["error"]
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
python -m pytest tests/providers/test_openai_agentic.py::test_tool_result_includes_query_field tests/providers/test_openai_agentic.py::test_snippet_truncated_to_300_chars tests/providers/test_openai_agentic.py::test_empty_search_results_returns_stable_shape tests/providers/test_openai_agentic.py::test_malformed_tool_args_returns_invalid_arguments tests/providers/test_openai_agentic.py::test_unsupported_tool_name -v
```

Expected: at least `test_tool_result_includes_query_field` and `test_snippet_truncated_to_300_chars` fail

- [ ] **Step 3: Rewrite `_execute_tool` in `openai_agentic.py`**

Replace the existing `_execute_tool` method entirely. Also add the new `_run_search` method above it:

```python
def _run_search(self, query: str) -> list:
    """Execute Brave search. Isolated for timeout wrapping and unit test patching."""
    return self._get_brave_client().search(q=query, count=5)

def _execute_tool(self, tool_call: Any, timeout_seconds: int = 30) -> str:
    """Execute a single tool call. Always returns a JSON string with a stable shape."""
    name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments)
    except Exception:
        return json.dumps({"error": "invalid_arguments"})

    if name == "WebSearch":
        query = args.get("query", "")
        if not query:
            return json.dumps({"query": "", "error": "invalid_arguments"})

        try:
            results = self._run_search(query)
        except Exception:
            return json.dumps({"query": query, "error": "search_failed"})

        truncated = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": (r.get("snippet") or "")[:300],
            }
            for r in results
        ]
        return json.dumps({"query": query, "results": truncated})

    return json.dumps({"error": f"unknown_tool: {name}"})
```

Note: the `timeout_seconds` parameter is wired in but the timeout wrapping (`concurrent.futures`) is added in the next task. This step just restructures the method cleanly.

- [ ] **Step 4: Run all tests, confirm they pass**

```bash
python -m pytest tests/providers/test_openai_agentic.py -v
```

Expected: all tests pass including the five new ones

- [ ] **Step 5: Commit**

```bash
git add scripts/providers/model_providers/openai_agentic.py \
        tests/providers/test_openai_agentic.py
git commit -m "fix: add query field, snippet truncation, and _run_search extraction to _execute_tool"
```

---

## Task 5: Add per-tool timeout + fix error vocabulary + `max_tool_calls_total`

The final batch of spec requirements: wrap `_run_search` with `concurrent.futures` timeout, add a cumulative tool-call counter, and replace freeform exception strings with the stable error vocabulary.

**Files:**
- Modify: `scripts/providers/model_providers/openai_agentic.py`
- Modify: `tests/providers/test_openai_agentic.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/providers/test_openai_agentic.py`. Add `import concurrent.futures` at the top of the file alongside existing imports.

```python
def test_tool_timeout_returns_stable_error():
    provider = OpenAIAgenticProvider({"model": "test-model", "api_key": "test-key"})

    mock_tc = MagicMock()
    mock_tc.function.name = "WebSearch"
    mock_tc.function.arguments = json.dumps({"query": "news"})

    # _run_search raising TimeoutError is re-raised by future.result(), caught as tool timeout
    with patch.object(provider, "_run_search", side_effect=concurrent.futures.TimeoutError()):
        payload = json.loads(provider._execute_tool(mock_tc, timeout_seconds=30))

    assert payload["query"] == "news"
    assert payload["error"] == "timeout"


def test_max_tool_calls_exceeded():
    provider = OpenAIAgenticProvider({"model": "test-model", "api_key": "test-key"})

    mock_brave = MagicMock()
    mock_brave.search.return_value = []
    provider._brave_client = mock_brave

    mock_tc = MagicMock()
    mock_tc.id = "call_1"
    mock_tc.type = "function"
    mock_tc.function.name = "WebSearch"
    mock_tc.function.arguments = json.dumps({"query": "news"})

    mock_msg = MagicMock()
    mock_msg.content = None
    mock_msg.tool_calls = [mock_tc]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=mock_msg, finish_reason="tool_calls")]
    )
    provider.client = mock_client

    # Limit to 2 tool calls; model always requests more
    result = provider.generate("prompt", allowed_tools="WebSearch", max_tool_calls_total=2, max_turns=20)

    assert result["error"] == "max_tool_calls_exceeded"


def test_max_turns_exceeded_returns_correct_error_string():
    provider = OpenAIAgenticProvider({"model": "test-model", "api_key": "test-key"})

    mock_brave = MagicMock()
    mock_brave.search.return_value = []
    provider._brave_client = mock_brave

    mock_tc = MagicMock()
    mock_tc.id = "call_1"
    mock_tc.type = "function"
    mock_tc.function.name = "WebSearch"
    mock_tc.function.arguments = json.dumps({"query": "news"})

    mock_msg = MagicMock()
    mock_msg.content = None
    mock_msg.tool_calls = [mock_tc]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=mock_msg, finish_reason="tool_calls")]
    )
    provider.client = mock_client

    result = provider.generate("prompt", allowed_tools="WebSearch", max_turns=2, max_tool_calls_total=100)

    assert result["error"] == "max_turns_exceeded"
    assert mock_client.chat.completions.create.call_count == 2


def test_api_exception_returns_provider_error():
    provider = OpenAIAgenticProvider({"model": "test-model", "api_key": "test-key"})

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("connection refused")
    provider.client = mock_client

    result = provider.generate("prompt")

    assert result["result"] == ""
    assert result["error"] == "provider_error"
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
python -m pytest tests/providers/test_openai_agentic.py::test_tool_timeout_returns_stable_error tests/providers/test_openai_agentic.py::test_max_tool_calls_exceeded tests/providers/test_openai_agentic.py::test_max_turns_exceeded_returns_correct_error_string tests/providers/test_openai_agentic.py::test_api_exception_returns_provider_error -v
```

Expected: all four fail (timeout not wrapped, no counter, wrong error strings)

- [ ] **Step 3: Add `concurrent.futures` import and update `_execute_tool` with timeout wrapping**

Add to the imports at the top of `openai_agentic.py`:

```python
import concurrent.futures
```

Replace the `_execute_tool` method body with the timeout-wrapped version. Keep `_run_search` unchanged:

```python
def _execute_tool(self, tool_call: Any, timeout_seconds: int = 30) -> str:
    """Execute a single tool call. Always returns a JSON string with a stable shape."""
    name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments)
    except Exception:
        return json.dumps({"error": "invalid_arguments"})

    if name == "WebSearch":
        query = args.get("query", "")
        if not query:
            return json.dumps({"query": "", "error": "invalid_arguments"})

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._run_search, query)
            try:
                results = future.result(timeout=timeout_seconds)
            except concurrent.futures.TimeoutError:
                return json.dumps({"query": query, "error": "timeout"})
            except Exception:
                return json.dumps({"query": query, "error": "search_failed"})

        truncated = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": (r.get("snippet") or "")[:300],
            }
            for r in results
        ]
        return json.dumps({"query": query, "results": truncated})

    return json.dumps({"error": f"unknown_tool: {name}"})
```

- [ ] **Step 4: Rewrite `generate()` with correct error vocab, `max_tool_calls_total`, and tool timeout wiring**

Replace the full `generate()` method:

```python
def generate(self, prompt: str, **kwargs) -> dict:
    timeout = kwargs.get("timeout", 120)
    max_turns = kwargs.get("max_turns", self._max_turns)
    max_tool_calls_total = kwargs.get("max_tool_calls_total", self._max_tool_calls_total)
    tool_timeout = kwargs.get("tool_timeout_seconds", self._tool_timeout_seconds)
    allowed_tools = kwargs.get("allowed_tools", "")
    system_prompt = kwargs.get("system_prompt")

    active_tools = []
    if allowed_tools and "WebSearch" in allowed_tools:
        active_tools.append(_WEBSEARCH_SCHEMA)

    messages: list = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    tool_calls_count = 0

    for _turn in range(max_turns):
        api_kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "timeout": timeout,
        }
        if active_tools:
            api_kwargs["tools"] = active_tools

        try:
            response = self.client.chat.completions.create(**api_kwargs)
        except Exception:
            return {"result": "", "error": "provider_error"}

        choice = response.choices[0]
        message = choice.message

        # Build a plain dict — OpenAI SDK returns Pydantic objects; third-party
        # endpoints need plain dicts in subsequent turns.
        msg_dict: dict = {"role": "assistant", "content": message.content}
        if message.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
        messages.append(msg_dict)

        if choice.finish_reason == "tool_calls" and message.tool_calls:
            for tc in message.tool_calls:
                tool_calls_count += 1
                if tool_calls_count > max_tool_calls_total:
                    return {"result": "", "error": "max_tool_calls_exceeded"}
                result_str = self._execute_tool(tc, timeout_seconds=tool_timeout)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": result_str,
                })
        elif message.content:
            return {"result": message.content}
        else:
            return {"result": "", "error": "provider_error"}

    return {"result": "", "error": "max_turns_exceeded"}
```

- [ ] **Step 5: Store config defaults in `__init__`**

The `generate()` method now reads `self._max_turns`, `self._max_tool_calls_total`, and `self._tool_timeout_seconds`. Make sure `__init__` sets all three:

```python
self._max_turns = config.get("max_turns", 10)
self._max_tool_calls_total = config.get("max_tool_calls_total", 8)
self._tool_timeout_seconds = config.get("tool_timeout_seconds", 30)
```

These lines should already be present from the existing skeleton. Confirm they are there; add any that are missing.

- [ ] **Step 6: Extract `_WEBSEARCH_SCHEMA` as module-level constant**

Move the WebSearch tool schema dict out of `generate()` into a module-level constant. This keeps `generate()` focused. Place it directly below the imports:

```python
_WEBSEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "WebSearch",
        "description": "Search the web for current events, facts, or context relevant to the newsletter.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."}
            },
            "required": ["query"],
        },
    },
}
```

In `generate()`, the `active_tools.append(...)` line becomes:

```python
active_tools.append(_WEBSEARCH_SCHEMA)
```

- [ ] **Step 7: Update `__init__.py` docstring**

In `scripts/providers/model_providers/__init__.py`, update the `make_provider` docstring to mention `openai_agentic`:

```python
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
```

- [ ] **Step 8: Run all tests**

```bash
python -m pytest tests/providers/ -v
```

Expected: all tests pass, no failures

- [ ] **Step 9: Commit**

```bash
git add scripts/providers/model_providers/openai_agentic.py \
        scripts/providers/model_providers/__init__.py \
        tests/providers/test_openai_agentic.py
git commit -m "feat: add per-tool timeout, max_tool_calls_total, and stable error vocabulary to OpenAIAgenticProvider"
```

---

## Self-Review Against Spec

**Spec §5.3 — Bounded loop requirements**
- `max_turns` (default 10): ✓ Task 5
- `max_tool_calls_total` (default 8): ✓ Task 5
- per-tool timeout: ✓ Task 5
- overall timeout: ✓ already present, wired through in Task 5

**Spec §6.2 — `generate()` kwargs**
- `timeout`: ✓ already present
- `max_turns`: ✓ already present
- `max_tool_calls_total`: ✓ Task 5
- `allowed_tools`: ✓ already present
- `system_prompt`: ✓ Task 3

**Spec §6.3 — Return contract / error vocabulary**
- `tool_timeout`: returned as `{"error": "timeout"}` in tool payload; `provider_error` for API calls ✓ Task 5
- `max_turns_exceeded`: ✓ Task 5
- `max_tool_calls_exceeded`: ✓ Task 5
- `provider_error`: ✓ Task 5

**Spec §8.1 — `query` field in tool results**: ✓ Task 4

**Spec §8.2 — Snippet truncation (300 chars)**: ✓ Task 4

**Spec §9.1 — Safeguards**
- tool timeout: ✓ Task 5
- empty results: ✓ Task 4
- malformed args: ✓ Task 4
- unsupported tool name: ✓ Task 4
- no text + no tool calls → `provider_error`: ✓ Task 5
- max turn + tool-call limits: ✓ Task 5
- SDK message serialization: ✓ Task 2

**Spec §13.1 — Unit tests**
- plain text completion: ✓ existing
- single tool call then answer: ✓ existing
- multiple sequential tool calls: ✓ `test_assistant_message_is_dict_in_multiturn` exercises two-turn path
- malformed tool args: ✓ Task 4
- unsupported tool name: ✓ Task 4
- empty search results: ✓ Task 4
- Brave client exception → `search_failed`: covered by `_execute_tool`'s `except Exception` branch (tested implicitly)
- max-turn cutoff: ✓ Task 5
- max-tool-calls cutoff: ✓ Task 5
- API call raises → `provider_error`: ✓ Task 5
- `query` field present in payload: ✓ Task 4
- `system_prompt` prepended as system message: ✓ Task 3

**DRY / code quality**
- `_load_api_key` duplication: ✓ Task 1
- WebSearch schema inline in `generate()`: ✓ Task 5 (module-level constant)

No gaps found.
