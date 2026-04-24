# MiniMax as a Pipeline Model Provider — Design

**Date:** 2026-04-23
**Status:** Approved
**Scope:** `config/pipelines/`, `scripts/providers/model_providers/`

## 1. Problem

We want to evaluate MiniMax as a model provider across the newsletter generation stack — research (reading/comprehension), rank (scoring), and synthesis (writing). Shaun has a MiniMax token plan with an API key. The current architecture already supports `OpenAICompatibleProvider`, so MiniMax integration should be additive, not a refactor.

The existing spec (2026-04-21) already describes how `OpenAICompatibleProvider` covers MiniMax via its OpenAI-compatible endpoint. This doc applies that design to the sophies-world pipeline, covering the specifics of what model to use where and how to configure it.

---

## 2. Goal

Enable MiniMax as a selectable model provider in the newsletter pipeline — for any or all of research, rank, and synthesis — via existing config without code changes. Confirm API compatibility, document the integration points, and flag any gaps.

---

## 3. Current Architecture

The pipeline is configured in `config/pipelines/default.yaml`. Per the 2026-04-21 design:

```yaml
models:
  synthesis:
    provider: claude
    model: opus
  ranking:
    provider: claude
    model: sonnet
```

`provider: openai_compatible` is already a supported option. MiniMax is a drop-in via that provider type.

`scripts/providers/model_providers/openai_compatible.py` implements the SDK integration:

```python
class OpenAICompatibleProvider(ModelProvider):
    def __init__(self, config: dict):
        base_url = config.get("base_url", "http://localhost:1234/v1")
        api_key = config.get("api_key", "not-needed")
        self.model = config.get("model")
        self.client = OpenAI(base_url=base_url, api_key=api_key)
```

Adding MiniMax means adding a new pipeline config or modifying the existing one — no Python changes needed.

---

## 4. Recommendation

### 4.1 API Endpoints

MiniMax exposes two endpoints — the OpenAI-compatible one is the integration path:

```
Base URL: https://api.minimax.io/v1
Auth: Bearer token (MINIMAX_API_KEY)
```

Auth is set via environment variable. MiniMax token plan holders get API keys from platform.minimax.io.

### 4.2 Model Selection

| Model | Context | Best For | Input $/1M | Output $/1M |
|-------|---------|----------|-----------|------------|
| `MiniMax-M2.7` | 196K | Full synthesis + agentic tasks | $0.30 | $1.20 |
| `MiniMax-M2.7-highspeed` | 196K | Production synthesis (stable variant) | same | same |
| `MiniMax-M2.5` | 128K | Research/rank phases (cheaper) | $0.15 | ~$0.50 |
| `MiniMax-M2.1` | 128K | Budget fallback | ~$0.05 | ~$0.20 |

For the newsletter pipeline:
- **Synthesis:** `MiniMax-M2.7` (or `-highspeed` for production stability)
- **Ranking:** `MiniMax-M2.5` (cost-effective for scoring tasks)
- **Research (reading):** `MiniMax-M2.5` (comprehension/extraction doesn't need M2.7)

### 4.3 Pipeline Config

In `config/pipelines/default.yaml` or a new `config/pipelines/minimax.yaml`:

```yaml
models:
  synthesis:
    provider: openai_compatible
    base_url: https://api.minimax.io/v1
    api_key: ${MINIMAX_API_KEY}
    model: MiniMax-M2.7
  ranking:
    provider: openai_compatible
    base_url: https://api.minimax.io/v1
    api_key: ${MINIMAX_API_KEY}
    model: MiniMax-M2.5
  # research (content_stage) uses openai_compatible if configured:
  content:
    provider: openai_compatible
    base_url: https://api.minimax.io/v1
    api_key: ${MINIMAX_API_KEY}
    model: MiniMax-M2.5
```

Or a dedicated `minimax` pipeline for easy swapping:

```yaml
# config/pipelines/minimax.yaml
pipeline:
  research_provider: brave_deterministic
  ranker_provider: model_rank_candidates  # uses models.ranking
  content_provider: hosted_integrated_search  # uses models.content
  render_provider: local_renderer
```

Run with: `python scripts/generate.py --child sophie --pipeline minimax`

---

## 5. Integration Notes

### 5.1 `max_completion_tokens` constraint

On the OpenAI-compatible endpoint (`/v1/chat/completions`), `max_completion_tokens` for M2.7 appears capped at **2048**. For synthesis (long-form writing), this may truncate output before the full newsletter is written.

**Options:**
1. Use `MiniMax-M2.5` for synthesis — it may have higher limits
2. Chunk synthesis: generate sections independently, assemble at render stage
3. Use the Anthropic-compatible endpoint (`https://api.minimax.io/anthropic`) — may have different limits

**Recommendation:** Test with current M2.7 limit first. If truncation is observed, fall back to M2.5 for synthesis or switch endpoints.

### 5.2 Prompt caching

MiniMax automatically caches repeated prefix content. The newsletter writing style guide (sent as a system message every run) will be cached. This can reduce input token costs by 40–60% on repeated-context runs.

Check `usage.prompt_tokens_details.cached_tokens` in API responses to verify.

### 5.3 Temperature settings

Per phase:
- **Synthesis:** `0.75` — balanced creativity/determinism
- **Ranking:** `0.2–0.3` — consistent scoring
- **Research (extraction):** `0.3` — factual, deterministic

These can be passed via `extra_body` in the OpenAICompatibleProvider or configured in the pipeline YAML if supported.

### 5.4 Function calling / tool use

M2.7 supports function calling and the `thinking` block (reasoning). Neither is required for the current newsletter pipeline phases — but M2.7's agentic capability is available if a future phase needs it.

### 5.5 Known MiniMax model IDs

Use exact model strings:
- `"MiniMax-M2.7"` — standard M2.7
- `"MiniMax-M2.7-highspeed"` — high-concurrency variant
- `"MiniMax-M2.5"` — M2.5
- `"M2-her"` — dialogue-optimized (not recommended for pipeline phases)

---

## 6. Migration Playbook

1. **Set environment variable:**
   ```bash
   export MINIMAX_API_KEY=your_key_here
   ```

2. **Add pipeline config** (optional — or modify `default.yaml` directly):
   ```bash
   cp config/pipelines/default.yaml config/pipelines/minimax.yaml
   # Update models.* to openai_compatible + MiniMax model IDs
   ```

3. **Test in isolation:**
   ```bash
   python -c "
   from scripts.providers.model_providers.openai_compatible import OpenAICompatibleProvider
   p = OpenAICompatibleProvider({'base_url': 'https://api.minimax.io/v1', 'api_key': '${MINIMAX_API_KEY}', 'model': 'MiniMax-M2.7'})
   r = p.generate('Extract the main topic from: Apple reports Q1 revenue up 8% year over year.', max_completion_tokens=256)
   print(r)
   "
   ```

4. **Run a trial generation:**
   ```bash
   python scripts/generate.py --child sophie --pipeline minimax --limit 1
   ```

5. **Verify output quality and check logs** (errors surface in `result.error` dict from `generate()`).
6. **Iterate** on pipeline config based on quality/cost results.

---

## 7. Open Questions

1. **`max_completion_tokens` for M2.7 synthesis:** Does 2048 token output limit suffice for a full newsletter? Need to test.
2. **Anthropic endpoint:** Does `https://api.minimax.io/anthropic` provide higher output limits for M2.7? Worth a test comparison.
3. **Token plan pricing:** Does Shaun's plan have included credits or different rates vs. public pricing? Dashboard verification needed.
4. **Per-phase vs. full-pipeline:** Should MiniMax power all three phases, or only specific ones where quality/cost is better?
5. **Quality vs. Opus/Claude:** No live head-to-head comparison yet. Recommend running the same input through both before committing to a full pipeline swap.

---

## 8. What Success Looks Like

- Pipeline runs successfully with MiniMax as the only model provider (all three phases)
- Output quality is comparable to Claude Opus for synthesis (assessed by spot-checking 1–2 issues)
- Token cost per issue is measurably lower with MiniMax vs. Claude
- No truncation artifacts in synthesis output (or chunking strategy confirmed working)
- `MINIMAX_API_KEY` is documented and the pipeline is selectable via `--pipeline minimax`
