# Config Architecture Refactor

**Date:** 2026-04-22
**Status:** Draft spec
**Scope:** Sophie’s World configuration layer (`config/`)
**Purpose:** Re-architect the configuration files to improve cohesion, separate infrastructure from persona definition, and make the system easier to scale and maintain.

---

## 1. Problem

The current configuration system (`config/children/sophie.yaml`, `config/sections.yaml`, `config/research.yaml`) has served its purpose for early iterations but is starting to show architectural strain. 

### Current pain points

1. **High Fragmentation of Section Definitions**
   Defining a single section (e.g., `world_watch`) requires editing three different blocks across two files:
   - `sections.yaml`: Defines display metadata, goals, and editorial rules.
   - `research.yaml` (`ranking.sections`): Defines ranking heuristics, boosts, and keywords.
   - `research.yaml` (`sections`): Defines search queries and freshness constraints.
   This high coupling and low cohesion make the config brittle, hard to read, and error-prone when adding or modifying sections.

2. **Leaky Concerns in Child Profiles**
   `sophie.yaml` mixes the child's **identity** and editorial defaults with **infrastructure details** (generation modes, LLM provider routing, specific model versions). A change to the infrastructure shouldn't require editing a child's profile.

3. **Redundant Source & Domain Management**
   Sources are defined in multiple places (`global_source_preferences`, `source_preferences` inside sections, `domains.kid_safe` in research). The boundary between what the LLM needs to know (editorial preferences) and what the search/ranking system needs to know (programmatic whitelists) is blurry.

---

## 2. Goal

Re-architect the `config/` directory to achieve **High Cohesion** (things that change together live together) and **Separation of Concerns** (child/profile/editorial defaults vs. section components vs. infrastructure). The system should easily support adding many new sections and changing pipeline infrastructure without touching unrelated files.

---

## 3. Product principles

### 3.1 Sections as first-class components
A newsletter "section" is a distinct feature. Its editorial intent, search strategy, and ranking logic should all be defined in one unified place.

### 3.2 Child profiles own child-specific editorial defaults, not infrastructure
A child profile should describe the child and the editorial feel of their newsletter:
- identity
- reading level
- tone
- emoji usage
- active newsletter sections
- interests

It should not know about provider routing, specific hosted models, or ranker implementation details.

### 3.3 Infrastructure is a separate layer
How we generate the newsletter (the pipeline, the LLMs, the providers, global ranking mechanics) is a system-level or environment-level concern, not a child-level concern.

---

## 4. Recommendation

Introduce a **Unified Component Model** for sections, extract infrastructure into a **Pipeline Config**, and keep **Child Profiles** focused on the child plus child-specific editorial defaults.

---

## 5. Proposed model

### 5.1 Unified Section Definitions (`config/sections/`)
Instead of a monolithic `sections.yaml` and `research.yaml`, treat each section as a cohesive component. Create a dedicated directory (`config/sections/`) where each section is a self-contained file.

Example: `config/sections/world_watch.yaml`
```yaml
id: world_watch
display:
  title: "🌍 World Watch"
  block_type: story_list
  link_style: link-green

editorial:
  goal: "Explain 2 real, material current events happening this week in kid-friendly language"
  content_rules:
    - MUST include serious topics if relevant
  source_preferences:
    - Time for Kids
    - NewsForKids.net

research:
  queries:
    - "world news for kids {date}"
    - "site:bbc.co.uk/newsround current events"
  freshness: pw
  count: 15

ranking:
  freshness_boost: 25
  keyword_match_boost: 8
  max_ranked: 4
  keywords:
    - war
    - climate
    - economy
```

### 5.2 Child Profiles (`config/children/`)
Strip infrastructure out of the child profiles. `sophie.yaml` represents the child and their child-specific editorial preferences.

Example: `config/children/sophie.yaml`
```yaml
id: sophie
name: Sophie
profile:
  age_band: 4th-grade
  location: Fremont, California
  cultural_context:
    - Singaporean family in the USA
  interests:
    active: [gymnastics, skiing, fun facts, saving money]
    inactive: [k-pop]

newsletter:
  active_sections:
    - weird_but_true
    - world_watch
    - usa_corner
  theme: default

editorial_overrides:
  reading_level: 4th grade
  tone: [warm, fun, curious]
  use_emojis: true
```

### 5.3 Infrastructure / Pipeline Configs (`config/pipelines/`)
Move the generation modes and model selections into a system-level configuration. This makes it easy to test different AI providers via a CLI flag (e.g., `--pipeline experimental`).

Pipeline configs should own:
- provider routing
- model selection
- global domain allow/block lists
- shared ranking defaults and global scoring mechanics

Section configs should still own section-local ranking/research intent, such as:
- freshness expectations
- section-specific keywords
- section-specific `max_ranked`
- section-specific query templates

This lets sections like `world_watch` express that they need fresher, current-event-oriented content, without scattering shared scoring mechanics across many files.

Example: `config/pipelines/default.yaml`
```yaml
pipeline:
  research_provider: brave_deterministic
  ranker_provider: heuristic_ranker
  content_provider: hosted_integrated_search
  render_provider: local_renderer

models:
  synthesis:
    provider: claude
    model: opus
  ranking:
    provider: claude
    model: sonnet

global_domains:
  kid_safe:
    - kids.nationalgeographic.com
    - kids.britannica.com
  blocked:
    - reddit.com
    - tiktok.com

global_ranking_defaults:
  source_boost: 20
  novelty_penalty: 30
```

---

## 6. Directory structure

### Interaction with staging / prod / approaches

This refactor should compose directly with the existing environment overlay model.
The same precedence rules continue to apply:

- approach override
- then staging override
- then prod baseline

Examples:

```text
config/pipelines/default.yaml
staging/config/pipelines/default.yaml
staging/approaches/<name>/config/pipelines/default.yaml

config/sections/world_watch.yaml
staging/config/sections/world_watch.yaml
staging/approaches/<name>/config/sections/world_watch.yaml
```

This means the config architecture refactor is not a separate environment model. It plugs into the staging/prod/approach system already in place.

### Old Structure
```text
config/
├── children/
│   └── sophie.yaml
├── research.yaml
├── sections.yaml
└── themes/
```

### New Structure
```text
config/
├── children/
│   └── sophie.yaml          # Child identity & editorial defaults
├── sections/
│   ├── world_watch.yaml     # Cohesive section config (display, editorial, search, rank)
│   ├── weird_but_true.yaml
│   └── ...
├── pipelines/
│   ├── default.yaml         # Provider routing, models, global ranking mechanics
│   └── experimental.yaml
└── themes/
    └── default.yaml
```

---

## 7. Migration playbook

1. **Create new structures:** Create the `config/sections/` and `config/pipelines/` directories.
2. **Extract Sections:** Write a one-off python script to parse the current `sections.yaml` and `research.yaml`, merge the keys for each section, and output the cohesive `config/sections/<section>.yaml` files.
3. **Extract Pipeline:** Manually extract the `generation` block from `sophie.yaml`, the global domains from `research.yaml`, and the global ranking defaults from `research.yaml` into `config/pipelines/default.yaml`.
4. **Update Codebase:** Update `config_loader.py` (or equivalent config resolution logic) to load from the new structure.
   - When resolving a run, load the child profile, the specified pipeline (default if omitted), and then map over the `active_sections` to load only the required section configs.
5. **Verify:** Run a generation using the new config structure and verify concrete invariants rather than requiring byte-for-byte identical outputs.
   - same resolved child profile semantics
   - same resolved active section set
   - same provider/ranker selection
   - same section-level research plan structure
   - same research packet schema
   - same artifact/output path semantics
   - same rendered issue shape
   - only acceptable content drift where hosted generation is nondeterministic
6. **Cleanup:** Delete the old `sections.yaml` and `research.yaml` files.

---

## 8. Non-goals

This spec does **not** introduce:
- A database-backed configuration system.
- Changes to the actual heuristic ranking logic or generation prompts (this is purely an architectural refactor of how inputs are structured).
- A UI for editing configurations.

---

## 9. Open questions

1. Should the CLI `generate.py` default to `pipelines/default.yaml` if no pipeline is specified?
   - Recommendation: Yes, `--pipeline default` should be the assumed default.
2. If we want to override a pipeline setting (e.g. use a different model just for this run), should we support CLI overrides like `--model synthesis=gpt-4o` or force the creation of an `experimental.yaml` pipeline?
   - Recommendation: Force the creation of a pipeline yaml file for durability and traceability, rather than complex CLI arg parsing.
3. Should we support an old+new config loader compatibility window during migration?
   - Recommendation: No. We are still early enough to do a straightforward cutover: migrate the files, update the loader, verify immediately, and remove the old structure.

---

## 10. Recommendation summary

**Recommended approach:**
- Break monolithic files into a **Unified Component Model** (`config/sections/*.yaml`).
- Keep child identity and editorial defaults in `config/children/sophie.yaml`.
- Move infrastructure and global defaults to `config/pipelines/default.yaml`.
- Let sections own section-local research/ranking intent, while pipelines own global mechanics.

This gives us a highly cohesive, easily extensible config architecture that correctly separates child definition from system infrastructure.

---

## 11. What success looks like

After the migration:
- Adding a new section involves creating exactly one file.
- Changing the primary LLM model involves editing exactly one file (`pipelines/default.yaml`), affecting all children instantly.
- The `config/` directory is intuitive enough that a new developer can understand the relationship between a child, a pipeline, a section, and the staging/prod/approach overlay model within 5 minutes.
