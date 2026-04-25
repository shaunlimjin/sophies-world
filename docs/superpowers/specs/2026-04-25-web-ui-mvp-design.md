# Web UI MVP Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A local-only React + FastAPI admin console for Sophie's World that covers config editing, multi-stage run creation with provider iteration, and approach comparison with promotion to staging.

**Architecture:** FastAPI imports existing stage modules directly (`research_stage`, `ranking_stage`, `content_stage`, `render_stage`) and exposes each stage as its own endpoint with SSE streaming. Existing CLI scripts (`generate.py`, `promote.py`) are refactored to call the same stage functions, keeping CLI and UI in sync. React (Vite) lives in `web/ui/`; FastAPI lives in `web/api/`; filesystem is the source of truth (no database).

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, Pydantic v2, React 18, Vite, TypeScript

---

## Scope

MVP covers three areas:

1. **Configs** — read/edit child profile, per-section configs, pipeline config, and research config as raw YAML
2. **Runs** — create named runs (approaches), execute the 4-stage pipeline sequentially or re-run individual stages, inspect artifacts at each stage with live SSE streaming
3. **Compare** — side-by-side comparison of two runs at any stage, with a Promote button to push the winner to staging (then staging to prod)

Out of scope for MVP: authentication, scheduling/cron management, send (Gmail), analytics.

---

## Project Structure

```
sophies-world/
  web/
    api/
      main.py              # FastAPI app factory, mounts routers
      routers/
        configs.py         # GET/PUT /api/configs/{file}
        runs.py            # GET /api/runs, POST /api/runs
        stages.py          # POST /api/runs/{name}/stages/{stage}, SSE stream, artifact fetch
        compare.py         # GET /api/compare — artifact fetch for two runs/stage
        promote.py         # POST /api/runs/{name}/promote
      services/
        config_service.py  # YAML read/write, file enumeration
        run_service.py     # run state, artifact path resolution
        stage_runner.py    # wraps stage functions, captures stdout for SSE
      requirements.txt     # fastapi, uvicorn[standard], pydantic, pyyaml
    ui/
      src/
        App.tsx
        components/
          ConfigEditor.tsx    # YAML textarea + Save/Discard
          RunList.tsx          # list of runs with status badges
          RunDetail.tsx        # two-column: pipeline list + artifact detail
          StagePanel.tsx       # left column: stage status list + Run All button
          ArtifactDetail.tsx   # right column: live log, JSON viewer, HTML iframe
          CompareView.tsx      # run pickers + shared stage selector + split panels
          PromoteButton.tsx    # diff preview + confirmation + promote call
        pages/
          ConfigsPage.tsx      # sidebar tab: Configs
          RunsPage.tsx         # sidebar tab: Runs (list + new run form)
          ComparePage.tsx      # sidebar tab: Compare
        api/
          client.ts            # typed fetch wrappers + SSE hook
      package.json
      vite.config.ts           # proxies /api/* to FastAPI in dev
  scripts/
    … (existing scripts — refactored to call stage functions, not subprocess)
```

---

## Backend Design

### Stage module refactor

Each stage module gains a callable function that the API (and refactored CLI) imports directly:

```python
# research_stage.py — new public function
def run_research_stage(config: dict, today: date, repo_root: Path, ...) -> dict:
    """Returns the research packet dict. Logs via a passed-in writer callable."""
    ...
```

The `stage_runner.py` service wraps these functions, captures log output line-by-line into an async generator, and feeds SSE.

### Run state

Run state is derived entirely from the filesystem — no database. A run exists if `artifacts/approaches/<name>/` exists. Stage completion is inferred from artifact presence:

| Stage | Artifact path |
|---|---|
| Research | `artifacts/approaches/<name>/research/sophie-YYYY-MM-DD-raw.json` (new — raw candidates before ranking) |
| Ranking | `artifacts/approaches/<name>/research/sophie-YYYY-MM-DD.json` (existing path — ranked packet) |
| Synthesis | `artifacts/approaches/<name>/issues/sophie-YYYY-MM-DD.json` |
| Render | `artifacts/approaches/<name>/newsletters/sophies-world-YYYY-MM-DD.html` |

**Note on stage separation:** The current `run_mode_b` bundles research + ranking into a single call. The stage module refactor must split these: `run_research_stage` returns raw candidates (written to `-raw.json`), and `run_ranking_stage` reads that file and writes the ranked packet to the existing path. This preserves backward compatibility with the CLI (which can call both in sequence) while giving the UI fine-grained control.

`run_service.py` reads these paths and returns a `RunState` Pydantic model with `stages: list[StageState]` where each `StageState` has `status: pending | running | done | failed` and `artifact_path: str | None`.

### API endpoints

```
GET  /api/configs                         → list of config file keys
GET  /api/configs/{file}                  → raw YAML string
PUT  /api/configs/{file}                  → write raw YAML string, return ok/error
GET  /api/runs                            → list[RunSummary]
POST /api/runs                            → { name, provider_overrides? } → RunSummary
GET  /api/runs/{name}                     → RunState (all 4 stage statuses + artifact presence)
POST /api/runs/{name}/stages/{stage}      → trigger stage, returns 202
GET  /api/runs/{name}/stages/{stage}/stream  → SSE: text/event-stream, lines of log output
GET  /api/runs/{name}/stages/{stage}/artifact → raw artifact (JSON or HTML)
GET  /api/compare?a={name}&b={name}&stage={stage} → { left: artifact, right: artifact }
POST /api/runs/{name}/promote             → { to: "staging" | "prod" } → diff preview
PUT  /api/runs/{name}/promote             → apply promotion (after confirmation)
```

Config file keys map to paths:
- `child` → `config/children/sophie.yaml`
- `pipeline` → `config/pipelines/default.yaml`
- `research` → `config/research.yaml`
- `section/{id}` → `config/sections/{id}.yaml`

### SSE streaming

Stage functions accept a `log: Callable[[str], None]` parameter and call it for each progress line. `stage_runner.py` bridges this into an `asyncio.Queue` fed to FastAPI's `EventSourceResponse`. The client `useSSE` hook in React appends lines to local state.

### CORS / dev setup

In dev: Vite (`localhost:5173`) proxies `/api/*` to FastAPI (`localhost:8000`). In prod: FastAPI serves the Vite build from `web/ui/dist/` as static files.

---

## Frontend Design

### Navigation

Persistent left sidebar with three items: **Configs**, **Runs**, **Compare**. Active item is highlighted. No routing library needed — simple `useState` for active page.

### Configs page

Tabs across the top for each config file (Child Profile, Pipeline, Research, and one tab per active section). Selecting a tab loads the YAML via `GET /api/configs/{file}` into a `<textarea>`. Save calls `PUT /api/configs/{file}`; Discard resets to last-fetched value. Validation error from the API (bad YAML) shows inline below the editor.

### Runs page

**List view:** Runs sorted by date descending. Each row shows run name, date, stage status badges (✓ done, ▶ running, ○ pending, ✗ failed), and an "Open" link.

**New Run form:** Name input + optional per-stage provider dropdowns (defaulting to current pipeline config values). Submit creates the run directory and navigates to the run detail.

**Run Detail (two-column):**
- **Left column (`StagePanel`):** Compact list of 4 stages with status icons and a "Run All" button at top. Clicking a stage selects it in the right panel. A running stage shows a spinner; done shows ✓; failed shows ✗ with a re-run option.
- **Right column (`ArtifactDetail`):** For the selected stage: provider label, re-run button, provider override dropdown. Below: live log (SSE) while running, or artifact viewer when done. Artifact viewer: JSON stages show pretty-printed JSON in a scrollable code block; Render stage shows the HTML in an `<iframe>`.

### Compare page

Two run-picker dropdowns at top left, shared stage tab selector at top right (Research | Ranking | Synthesis | Render). Selecting a stage fetches both artifacts via `GET /api/compare`. Below: split two-panel layout. For Render stage: two `<iframe>` panels. For other stages: two scrollable code blocks.

"Promote [run name] → Staging" button appears when a run is selected in either picker. Clicking it calls `POST /api/runs/{name}/promote` to get a diff, shows the diff in a modal with Confirm/Cancel, then `PUT` to apply.

---

## Stage Provider Options

The UI populates provider dropdowns from a static list (no discovery endpoint needed for MVP):

| Stage | Options |
|---|---|
| Research | `brave_deterministic` |
| Ranking | `heuristic_ranker`, `hosted_model_ranker` |
| Synthesis | `hosted_packet_synthesis`, `hosted_integrated_search` |
| Render | `local_renderer` |

Model overrides (synthesis model, ranking model) are editable fields in the New Run form: provider name + model name (e.g. `claude` / `opus`).

---

## Error Handling

- YAML save: API parses before writing; returns `400` with parse error message shown inline in the editor.
- Stage failure: stage function raises, `stage_runner.py` catches, writes `failed` status to a sentinel file (`<artifact_dir>/.stage-{stage}.failed`), SSE emits a final `error:` event. UI shows ✗ badge with last log line as tooltip.
- Stage already running: `POST /api/runs/{name}/stages/{stage}` returns `409` if a sentinel file `<artifact_dir>/.stage-{stage}.running` exists.
- Run name collision: `POST /api/runs` returns `409` if directory already exists.

---

## Dev Startup

```bash
# Terminal 1 — API
cd web/api && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — UI
cd web/ui && npm install
npm run dev   # http://localhost:5173
```

A single `web/dev.sh` script runs both with `concurrently`.

---

## Testing

- **API unit tests** (`tests/test_web_api.py`): use FastAPI `TestClient`; mock stage functions to return fixture artifacts; cover each endpoint's happy path and error cases (409 collision, 400 bad YAML, 404 missing run).
- **Stage runner tests** (`tests/test_stage_runner.py`): verify SSE line output and sentinel file lifecycle.
- **No frontend tests in MVP** — manual testing of golden path (create run → run all stages → compare two runs → promote).
