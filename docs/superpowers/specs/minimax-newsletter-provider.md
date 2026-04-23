# SPEC: MiniMax as a Newsletter Pipeline Model Provider

**Author:** Calvin  
**Date:** 2026-04-23  
**Status:** Research complete — ready for implementation decision

---

## Context

We want to evaluate MiniMax as a model provider across the newsletter generation stack — specifically in research, rank, and synthesis phases. Shaun has a MiniMax token plan with an API key and wants current API documentation applied.

This doc covers:
1. Current MiniMax API capabilities and limits
2. Mapping those capabilities to newsletter pipeline phases
3. Integration patterns and code examples
4. Pricing
5. Recommended next steps

---

## 1. MiniMax API — What We Have

### Base URL
```
https://api.minimax.io/v1          # OpenAI-compatible
https://api.minimax.io/anthropic    # Anthropic-compatible
```

### Authentication
- Bearer token: `Authorization: Bearer ${MINIMAX_API_KEY}`
- API key from platform.minimax.io dashboard

### Available Models (text, 2026)

| Model | Context | Key Feature | Input $/1M | Output $/1M |
|-------|---------|-------------|-----------|------------|
| `MiniMax-M2.7` | 196,608 tokens | Self-evolving agentic, reasoning | $0.30 | $1.20 |
| `MiniMax-M2.7-highspeed` | 196,608 tokens | High-concurrency stable variant | ~same | ~same |
| `MiniMax-M2.5` | 128K tokens | Lower cost | $0.15 | ~$0.50 |
| `MiniMax-M2.1` | 128K tokens | Budget | ~$0.05 | ~$0.20 |
| `M2-her` | 64K tokens | Dialogue/roleplay-optimized | — | — |

*Prices vary slightly by provider (platform.minimax.io vs AIMLAPI vs OpenRouter).*

### Protocol Support
- **OpenAI-compatible:** `POST /v1/chat/completions` — drop-in for OpenAI SDK
- **Anthropic-compatible:** `POST /v1/messages` — supports tool use and `thinking` block
- Streaming: supported (`stream: true`)
- Function/tools calling: supported (see Section 2)

### Key Capabilities
- **Prompt caching:** For repeated large context (up to 40–60% cost savings on repeated prompts)
- **Reasoning split:** `reasoning_split: true` separates think block from output
- **Tool use / function calling:** Full agentic loop (see function call guide)
- **Multi-modal:** Text-only for M2.7 — no image/audio input (use Hailuo models separately for media)

---

## 2. Mapping to Newsletter Pipeline Phases

### Phase 1: Research (web search, page fetch)
**Model fit:** `MiniMax-M2.7` or `MiniMax-M2.5`

MiniMax can be used as a reading/comprehension model here — given a corpus of fetched content, it can summarize, extract key facts, and structure notes. The API is stateless per call, so you'd pass in the content as messages.

**Integration pattern:**
```python
from openai import OpenAI
client = OpenAI(api_key=os.environ["MINIMAX_API_KEY"], api_base="https://api.minimax.io/v1")

response = client.chat.completions.create(
    model="MiniMax-M2.7",
    messages=[
        {"role": "system", "content": "You are a research assistant. Extract key facts and data points from the provided content."},
        {"role": "user", "content": fetched_content_here}
    ],
    max_completion_tokens=2048,
    temperature=0.3
)
```

**Considerations:**
- Context window is ample (196K for M2.7) — can fit large research documents in a single call
- `temperature=0.3` recommended for factual extraction (lower = more deterministic)
- M2-her is NOT ideal here — it's dialogue-optimized, not extraction-optimized

### Phase 2: Rank (score, sort, filter sources)
**Model fit:** `MiniMax-M2.7` (with reasoning_split) or `MiniMax-M2.5`

Rank is a classification/scoring task. You can either:
- Prompt the model to output a structured score per item, or
- Use function calling to return structured JSON with scores

**Integration pattern — structured scoring:**
```python
response = client.chat.completions.create(
    model="MiniMax-M2.7",
    messages=[
        {"role": "system", "content": "Score each item from 1-10 on relevance, timeliness, and credibility. Output JSON: [{\"url\": \"...\", \"score\": N, \"reason\": \"...\"}]"},
        {"role": "user", "content": list_of_sources_here}
    ],
    response_format={"type": "json_object"},
    max_completion_tokens=1024,
    temperature=0.2
)
```

**Considerations:**
- `response_format={"type": "json_object"}` for structured output
- `temperature=0.2` for consistent scoring
- With `reasoning_split: true`, you can also get the model's reasoning trace per score

### Phase 3: Synthesis (write the newsletter)
**Model fit:** `MiniMax-M2.7` (creative reasoning + length) or `MiniMax-M2.5` (cost savings)

This is the most demanding phase — long-form coherent writing with a specific tone.

**Integration pattern:**
```python
response = client.chat.completions.create(
    model="MiniMax-M2.7",
    messages=[
        {"role": "system", "content": "You are a financial newsletter writer. Write a well-structured, engaging newsletter in the provided style and structure. Be concise but informative."},
        {"role": "user", "content": f"Topic: {topic}\n\nResearch notes:\n{research_notes}\n\nRanked sources:\n{ranked_sources}"}
    ],
    max_completion_tokens=4096,
    temperature=0.75  # moderate creativity
)
```

**Considerations:**
- `max_completion_tokens` must be raised for long output (max is 2048 on the OpenAI-compatible endpoint for M2.7 — verify current limit; M2.5 supports more)
- `temperature=0.7–0.8` for natural, engaging writing
- For higher throughput, use `MiniMax-M2.7-highspeed` as the stable production variant

### Full Newsletter Generation (end-to-end)
**Model fit:** `MiniMax-M2.7` exclusively — this requires the full agentic capability

For a single-shot generation from raw research to final output, M2.7's agentic loop with tool use is the right fit:

```python
response = client.chat.completions.create(
    model="MiniMax-M2.7",
    messages=[
        {"role": "system", "content": "You are a financial newsletter writer. Given the provided research materials and ranking criteria, produce a complete, publication-ready newsletter."},
        {"role": "user", "content": f"Materials:\n{all_content}\n\nWriting style: {style_guide}"}
    ],
    tools=[
        {
            "type": "function",
            "function": {
                "name": "save_to_file",
                "description": "Save the newsletter draft to a file",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}
            }
        }
    ],
    max_completion_tokens=4096,
    temperature=0.75
)
```

---

## 3. Integration Patterns

### SDK Choice
- **OpenAI Python/JS SDK** works directly — just set `api_base`
- **Anthropic SDK** works via `https://api.minimax.io/anthropic` base URL
- **liteLLM** supports `minimax/MiniMax-M2.7` natively (good if you want a unified interface)

### Configuration for Newsletter App
In the newsletter generation scripts, a provider config would look like:

```python
PROVIDERS = {
    "minimax": {
        "api_base": "https://api.minimax.io/v1",
        "api_key": os.environ["MINIMAX_API_KEY"],
        "model": "MiniMax-M2.7",
        "models": {
            "research": "MiniMax-M2.7",
            "rank": "MiniMax-M2.7",
            "synthesis": "MiniMax-M2.7",
            # Or use M2.5 for cost-sensitive phases
            "rank-cheap": "MiniMax-M2.5",
        }
    }
}
```

### Prompt Caching (cost optimization)
For repeated system prompts or large context documents:
```python
# Prefix the messages array with cached content markers
# (MiniMax caches repeated prefix content automatically)
# Monitor usage resp headers for cost tracking
```

---

## 4. Prompt Caching with MiniMax

MiniMax offers prompt caching for repeated large contexts. From the AIMLAPI docs:

> M2.7 supports efficient prompt caching, making it cost-effective for large-scale usage. In production agentic workflows with repeated large context, this can reduce inference costs by 40–60%.

**Usage pattern:**
- Send the large base context as a system message or initial user message
- MiniMax automatically caches the prefix
- Subsequent calls with the same prefix reuse cached tokens
- Check `usage.prompt_tokens_details.cached_tokens` in the response to verify

**Newsletter use case:**
- Store the writing style guide as a semi-static system prompt
- It gets cached across runs automatically
- Significant savings if you run daily newsletters

---

## 5. Pricing Summary

| Model | Input | Output | Notes |
|-------|-------|--------|-------|
| MiniMax-M2.7 | $0.30/1M | $1.20/1M | Flagshiip — full agentic |
| MiniMax-M2.7-highspeed | same | same | Production stable variant |
| MiniMax-M2.5 | $0.15/1M | ~$0.50/1M | Budget option |
| MiniMax-M2.1 | ~$0.05/1M | ~$0.20/1M | Lowest cost |

**Token plan subscribers:** May have different rates or included credits — check platform.minimax.io dashboard for Shaun's specific plan pricing.

**Estimation for newsletter:**
- Research: ~50K tokens input, 2K output → ~$0.015
- Rank: ~30K tokens input, 1K output → ~$0.010
- Synthesis: ~30K tokens input, 4K output → ~$0.025
- **Total per issue: ~$0.05** (with M2.7) — very cheap

---

## 6. Gaps & Open Questions

1. **Model limits verification:** `max_completion_tokens` max appears to be 2048 on the OpenAI-compatible endpoint for M2.7 — need to confirm this allows sufficient synthesis output. If not, M2.5 may be needed for synthesis.

2. **Anthropic-compatible endpoint:** For function calling with thinking traces, the Anthropic endpoint (`https://api.minimax.io/anthropic`) may be required. Worth testing both.

3. ** Shaun's token plan specifics:** Dashboard rates may differ from listed prices. Should verify actual plan pricing before full cost建模.

4. **Integration testing:** No live test yet — need to verify actual token usage and output quality with MiniMax before committing to full pipeline swap.

5. **Provider routing:** Current pipeline/ approaches may need a new `minimax` provider entry. The approach for specifying per-phase model selection was mentioned as already updated in recent README changes.

---

## 7. Recommended Next Steps

1. **Verify API key and plan pricing** on platform.minimax.io
2. **Run a quick quality test** — pick one research doc, run it through MiniMax-M2.7 vs current model, compare outputs
3. **Check `max_completion_tokens` limit** — if synthesis output needs >2048 tokens, either chunk synthesis or use M2.5/M2.1 for that phase
4. **Add provider config** to newsletter pipeline with MiniMax as a selectable provider
5. **Update SPEC with test results** before full rollout

---

## Appendix: Quick Test Snippet

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["MINIMAX_API_KEY"],
    api_base="https://api.minimax.io/v1"
)

# Test research extraction
test_content = "Apple reported Q1 2026 earnings: revenue 124.3B, EPS 2.31, services revenue up 18% YoY."

response = client.chat.completions.create(
    model="MiniMax-M2.7",
    messages=[
        {"role": "system", "content": "Extract key financial metrics from this text."},
        {"role": "user", "content": test_content}
    ],
    max_completion_tokens=256,
    temperature=0.3
)

print(response.choices[0].message.content)
```
