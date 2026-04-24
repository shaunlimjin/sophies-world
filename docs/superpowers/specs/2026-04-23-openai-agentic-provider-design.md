# OpenAI Agentic Provider Design

**Date:** 2026-04-23
**Status:** Draft spec — updated 2026-04-23 post implementation review
**Scope:** `scripts/providers/model_providers/`, Mode A provider path, and tool-backed hosted generation
**Purpose:** Define a tool-capable OpenAI-style provider that can participate in Sophie’s World’s integrated-search flow without overloading the existing thin `OpenAICompatibleProvider`.

---

## 1. Problem

The current `OpenAICompatibleProvider` is intentionally thin. It wraps `/v1/chat/completions` endpoints for deterministic prompt-response tasks such as ranking and packet synthesis, but it does **not** implement:
- multi-turn message history
- tool calling
- tool result continuation
- loop control for agentic workflows

That is the right tradeoff for deterministic tasks, but it means Sophie’s World’s current **Mode A** path cannot be cleanly evaluated against OpenAI-compatible backends such as MiniMax.

Today, Mode A depends on a provider behavior contract that is more than “one model call with a prompt.” It includes:
- multi-turn continuation
- web-search/tool access
- bounded autonomous iteration
- termination rules
- output parsing back into the issue JSON contract

So the gap is real, but the solution should preserve the simplicity of `OpenAICompatibleProvider` rather than stretching it into two jobs.

---

## 2. Goal

Introduce a separate `OpenAIAgenticProvider` that:
- implements a bounded OpenAI-style tool loop
- can serve as the **tool-capable hosted generation provider path** for Sophie’s World experiments
- keeps `OpenAICompatibleProvider` unchanged for deterministic tasks
- makes it possible to test OpenAI-compatible backends (for example MiniMax or native OpenAI-compatible endpoints) in a Mode-A-like flow

---

## 3. Non-goals

This spec does **not** assume or promise:
- immediate quality parity with the current Claude-backed Mode A path
- support for every OpenAI-compatible backend on day one
- general-purpose agent tooling beyond what Sophie’s World actually needs
- replacing Brave deterministic research in Mode B

The first implementation is an **enablement path**, not a proof that MiniMax/OpenAI-compatible backends will match Claude Mode A quality.

---

## 4. Recommendation

Add a new provider class, `OpenAIAgenticProvider`, alongside the current `OpenAICompatibleProvider`.

### Why a new class instead of expanding the existing provider?

Because these are meaningfully different contracts:

- `OpenAICompatibleProvider`
  - single prompt → single response
  - deterministic tasks
  - minimal assumptions

- `OpenAIAgenticProvider`
  - multi-turn conversation state
  - tool schemas and tool execution
  - bounded autonomous loop
  - Mode-A-like orchestration behavior

Keeping them separate preserves clarity and avoids turning the generic provider into a kitchen sink.

---

## 5. Architecture

### 5.1 New class: `OpenAIAgenticProvider`

Create:
- `scripts/providers/model_providers/openai_agentic.py`

Register it in `PROVIDER_MAP` as:
- `openai_agentic`

It should share basic config shape with `OpenAICompatibleProvider`:
- `base_url`
- `api_key`
- `model`

but expose a different execution model in `generate()`.

### 5.2 High-level loop

The provider’s `generate()` method should:
1. initialize a `messages` array with the user prompt (and system prompt if the caller supplies one)
2. call the model with configured tool schemas
3. inspect the assistant response
4. if the model requests tools:
   - append the assistant tool-call message
   - execute each approved tool locally
   - append normalized tool-result messages
   - continue
5. if the model returns final text:
   - stop and return the text result
6. if limits are hit or errors occur:
   - return a structured error/fallback signal

### 5.3 Bounded loop requirements

The loop must be bounded by explicit safety limits:
- `max_turns` (default 10) — hard ceiling on conversation turns; returns `max_turns_exceeded` error when hit
- `max_tool_calls_total` (default 8) — cumulative tool-call ceiling across all turns; prevents a model that calls 3+ tools per turn from bypassing `max_turns`
- per-tool timeout (via `tool_timeout_seconds`, default e.g. 30s) — individual tool execution deadline; Brave calls in particular can hang
- overall request timeout (`timeout`, default 120s) — end-to-end deadline passed to the OpenAI client

This provider should fail safely rather than looping optimistically.

> **Implementation note:** `max_tool_calls_total` and per-tool timeout are required safety features. A provider missing either can exceed intended cost and latency bounds even with a small `max_turns` value.

---

## 6. Provider contract

### 6.1 Supported config fields

Minimum:

```yaml
provider: openai_agentic
base_url: https://api.minimax.io/v1
model: MiniMax-M2.7
```

Optional:
- `api_key`
- `temperature`
- `top_p`
- `max_turns` (default 10)
- `max_tool_calls_total` (default 8)
- `tool_timeout_seconds` (default 30)
- `allowed_tools`

### 6.2 Supported `generate()` kwargs

This provider should explicitly support:
- `timeout` — passed through to OpenAI client
- `max_turns` — overrides config default for this call
- `max_tool_calls_total` — overrides config default for this call
- `allowed_tools` — controls which tool schemas are included in the API call
- `system_prompt` — if provided, prepended as a `{"role": "system", ...}` message before the user turn

`system_prompt` is required for Sophie's World Mode A compatibility: the content stage passes editorial context (reading level, tone, section definitions) via the system message. Without it, the provider cannot replicate Mode A behavior.

The contract must be documented clearly in code so callers know which fields are meaningful.

### 6.3 Return contract

Successful return:

```python
{"result": "...final text from model..."}
```

Error return:

```python
{"result": "", "error": "tool_timeout"}
```

The `error` field must use a stable, enumerated vocabulary. Callers branch on these strings — freeform exception messages (`str(e)`) are not acceptable here:

| Error string | Trigger |
|---|---|
| `tool_timeout` | Per-tool execution exceeded `tool_timeout_seconds` |
| `tool_error` | Tool execution raised an unexpected exception |
| `max_turns_exceeded` | Loop hit `max_turns` limit without final answer |
| `max_tool_calls_exceeded` | Loop hit `max_tool_calls_total` limit |
| `provider_error` | The upstream API call itself failed |

API exceptions must be caught and mapped to `provider_error`; they must not leak raw exception text into the `error` field.

---

## 7. Tool surface

### 7.1 First implementation: explicit, narrow tool set

The first version should support a **small, explicit** tool surface only.

Recommended first slice:
- `WebSearch`

Optional second tool after validation:
- `WebFetch`

### 7.2 Why start narrow?

Because the goal is not to build a general-purpose web agent. The goal is to give Sophie’s World a Mode-A-like tool-backed generation path that is:
- testable
- bounded
- good enough to evaluate provider quality

### 7.3 `WebSearch` tool schema

```json
{
  "type": "function",
  "function": {
    "name": "WebSearch",
    "description": "Search the web for current events, facts, or context relevant to the newsletter.",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "The search query."
        }
      },
      "required": ["query"]
    }
  }
}
```

### 7.4 Tool execution backend

`WebSearch` should use existing local infrastructure:
- `BraveSearchClient`

That is the cleanest first implementation because the repo already depends on Brave search elsewhere.

---

## 8. Tool result contract

This is the most important missing piece in many agent-loop specs, so we should be explicit.

### 8.1 Normalized search result payload

Tool results passed back to the model must be normalized into a bounded JSON structure. The `query` field is required — the model benefits from seeing what it searched for, especially when results are sparse:

```json
{
  "query": "tariffs kids news april 2026",
  "results": [
    {
      "title": "...",
      "url": "...",
      "snippet": "..."
    }
  ]
}
```

A result payload without `query` is non-conformant.

### 8.2 Truncation policy

To avoid prompt bloat, tool results must be bounded:
- fixed max result count: 5 results per search call
- snippet truncation: cap each snippet at a fixed character limit (e.g. 300 characters) before serializing into the tool result message
- no raw oversized payloads: the normalized result must be the only thing in the tool message content, not a dump of the full Brave response object

### 8.3 Error payloads

If a tool fails, the tool result should still be normalized, e.g.:

```json
{
  "query": "...",
  "error": "timeout"
}
```

or:

```json
{
  "query": "...",
  "results": []
}
```

The model loop should see a stable shape, not arbitrary Python exceptions serialized into chat.

---

## 9. Failure handling and loop control

### 9.1 Required safeguards

The provider must define explicit behavior for:
- tool timeouts — return `tool_timeout` error; do not let Brave calls block indefinitely
- empty search results — return normalized `{"query": "...", "results": []}` and continue the loop
- malformed tool arguments — return `{"error": "invalid_arguments"}` as the tool result; do not raise
- unsupported tool names — return `{"error": "unknown_tool: <name>"}` as the tool result; do not raise
- provider response without text and without tool calls — treat as `provider_error` and stop
- repeated tool loops that fail to converge — `max_turns` and `max_tool_calls_total` together enforce this ceiling
- assistant message serialization — the OpenAI SDK returns Pydantic model objects, not dicts; call `.model_dump()` (or equivalent) before appending assistant messages to the `messages` list, otherwise multi-turn calls will fail or behave unpredictably

### 9.2 Recommended fallback behavior

If the loop fails safely, return a structured provider error and let the caller decide whether to:
- fail the run
- fall back to another provider
- fall back to a non-agentic mode

This is better than silently returning half-finished text.

### 9.3 Brave/search-specific caution

If this provider uses local Brave-backed search, then “integrated search” is not literally the same thing as the current Claude-hosted search path. It is a **tool-backed local search approximation** of that capability.

The spec should be honest about that difference.

---

## 10. Relation to Sophie’s World Mode A

### 10.1 This is intended as a Mode-A-like provider path

This provider is meant to serve as a **Mode-A-like** hosted generation path for Sophie’s World.

That means the first implementation should aim to be compatible with the existing content-stage expectations:
- prompt construction
- allowed-tools wiring
- final JSON output parsing
- error surface

### 10.2 But it is not automatically parity-equivalent

Even if the plumbing is correct, this does **not** imply parity with the current Claude-backed Mode A path on:
- content quality
- search judgment
- citation quality
- tool usage discipline
- latency
- cost

So the correct framing is:
- **provider-path compatibility target**
- **quality parity to be evaluated separately**

---

## 11. Pipeline integration

After provider registration, the factory can support:

```yaml
models:
  synthesis:
    provider: openai_agentic
    model: MiniMax-M2.7
    base_url: https://api.minimax.io/v1
```

and a pipeline such as:

```yaml
pipeline:
  content_provider: hosted_integrated_search
```

This should be introduced through a staging approach first, not flipped into prod baseline immediately.

---

## 12. Recommended rollout

### Phase 1 — enablement prototype

Implement:
- `OpenAIAgenticProvider`
- `WebSearch`
- bounded loop controls
- basic tests

Target:
- prove the provider can complete a tool-backed generation loop end-to-end

### Phase 2 — Sophie’s World Mode A experiment

Create a staging approach that uses:
- `provider: openai_agentic`
- MiniMax or another OpenAI-compatible backend

Then compare against current Claude-backed Mode A on:
- issue quality
- schema validity
- search quality
- latency/cost

### Phase 3 — optional `WebFetch`

Only add a second tool if evaluation shows `WebSearch` alone is not sufficient.

That keeps the first implementation tight.

---

## 13. Testing requirements

### 13.1 Unit tests

Use `unittest.mock` to simulate:
- plain text completion without tool use (no `tools` key in API call)
- single tool call then final answer
- multiple sequential tool calls across multiple turns
- malformed tool args (invalid JSON in `tool_call.function.arguments`)
- unsupported tool name in tool call
- empty search results from Brave (provider returns `{"query": "...", "results": []}`)
- Brave client raises exception (provider returns `tool_error`)
- max-turn cutoff (loop hits `max_turns`, returns `max_turns_exceeded`)
- max-tool-calls cutoff (loop hits `max_tool_calls_total`, returns `max_tool_calls_exceeded`)
- API call raises exception (provider returns `provider_error`)
- tool result `query` field is present in returned payload
- `system_prompt` kwarg is prepended as a system message

### 13.2 Sophie’s World integration tests

Add tests or manual validation for:
- issue JSON schema compliance
- no runaway tool loop
- stable error behavior when search fails
- clean final parse into the existing content pipeline

### 13.3 Evaluation bar

Before calling this ready for real use, verify:
- output is parseable
- citation/link quality is acceptable
- tool behavior is bounded and predictable
- cost/latency are not obviously worse than the value it adds

---

## 14. Open questions

1. Is `WebSearch` alone enough for acceptable Mode-A-like quality, or will we need `WebFetch` quickly?
2. Which OpenAI-compatible backend should be the first target: MiniMax, native OpenAI, or both?
3. Should the provider support richer system-message/control-message structure up front, or keep v1 minimal?
4. Should fallback behavior live inside the provider, or remain entirely at the caller/pipeline level?
5. If MiniMax/OpenAI-compatible quality is materially below Claude in Mode A, do we still keep this provider for experimentation only?

---

## 15. What success looks like

After this work:
- Sophie’s World has a separate tool-capable OpenAI-style provider path
- `OpenAICompatibleProvider` remains thin and clean for deterministic tasks
- we can run a bounded Mode-A-like experiment against OpenAI-compatible backends
- tool result payloads and failure behavior are explicit instead of ad hoc
- provider-path compatibility is achieved without pretending quality parity is guaranteed
