# Sophie's World Admin Console Design Spec

**Date:** 2026-04-20  
**Status:** Draft  
**Purpose:** Define a high-quality admin console concept for Sophie’s World that can be used as input to Google Stitch or similar UI generation/design tools.

---

## 1. Overview

Sophie's World has evolved from a simple weekly newsletter generator into a small editorial system with:

- multiple generation modes
- research/ranking/synthesis stages
- test vs production workflows
- artifact inspection needs
- review and comparison workflows
- operational sending controls
- increasing risk of repeated stories across nearby issues

The product now needs an **admin console** that makes the system legible, controllable, and safe to operate.

This is **not** a consumer UI for children or recipients.
It is an **operator/admin interface** for a parent-builder managing content generation, experimentation, review, and delivery.

---

## 2. Product intent

The admin console should feel like a hybrid of:

- a lightweight editorial studio
- an AI content operations tool
- a safe control panel for recurring newsletter production

It should help the operator:

- understand what the system generated
- compare different generation modes side by side
- inspect intermediate artifacts when needed
- configure production defaults
- run ad hoc experiments safely
- catch repetition before sending
- manage send scheduling and recipient configuration
- tune child/profile/editorial settings without editing raw files

The UI should make the product feel **intentional and trustworthy**, not like a loose collection of scripts.

---

## 3. Primary user

### Primary user
A technically capable parent-builder / operator running Sophie’s World.

### User goals
- generate issues reliably
- compare outputs before choosing defaults
- avoid repeated stories across recent issues
- tweak profile and editorial settings easily
- schedule and deliver newsletters cleanly
- debug without reading raw logs unless necessary

### User mindset
The user is not looking for playful novelty. They want:
- confidence
- visibility
- control
- editorial quality
- operational simplicity

---

## 4. Core design principles

### 4.1 Calm, editorial, premium
The UI should feel polished, modern, and calm, with strong readability and subtle warmth.
Think:
- editorial tooling
- polished AI ops
- premium productivity software

Not:
- enterprise admin sludge
- bright playful children’s UI
- noisy dashboards with too many metrics

### 4.2 Review and comparison are central
The most important product workflow is no longer “run generation.”
It is:
- inspect outputs
- compare modes
- evaluate novelty / repetition risk
- decide what should become production

The UI should treat **Review & Compare** as a first-class center of gravity.

### 4.3 Production vs test must be obvious
The system has both production and test behavior.
The UI must make that distinction unmissable.
This should show up in:
- filters
- badges
- action language
- lifecycle states
- run creation flows

### 4.4 Intermediate artifacts matter
This system is multi-stage.
The admin console must make it possible to inspect:
- final HTML output
- structured issue artifact JSON
- research packet JSON
- run metadata and logs

Without forcing the operator into raw files unless they want them.

### 4.5 Repetition awareness is a product feature
The biggest current quality risk is **story collision across nearby issues**.
The UI should explicitly surface:
- repeated URLs
- repeated events/themes
- likely cosmetic rewrites
- novelty risk at issue level

This is not a hidden technical detail. It is a core product concern.

---

## 5. Information architecture

Use a **desktop-first app shell** with:
- left sidebar navigation
- top bar for context + actions
- large main workspace area
- optional right-side inspector panels where useful

### Primary navigation
1. **Dashboard**
2. **Issues**
3. **Runs / Experiments**
4. **Review & Compare**
5. **Delivery**
6. **Content Setup**
7. **System / Providers**

---

## 6. Screen specifications

## 6.1 Dashboard

### Purpose
Provide a high-level operating view of the system.
This is the landing page for someone checking status or deciding what to do next.

### Key content
- next scheduled production send
- latest production issue summary
- latest test runs summary
- current default generation mode
- recipient / sender summary
- current novelty risk summary
- recent activity feed

### Suggested modules
- **Hero status card**
  - “Next production issue sends Friday at 7:00 PM PT”
  - status badge: Ready / Needs review / Blocked
- **Current default mode card**
  - Mode B1 highlighted
  - short explanation of why it is current default
- **Recent runs strip**
  - latest Mode A / B1 / B2 test results
  - success/failure badges
- **Latest issue preview card**
  - thumbnail + metadata + quick actions
- **Novelty risk card**
  - story collision warning level
  - repeated-theme summary
- **Activity feed**
  - generation completed
  - test run created
  - issue promoted
  - send completed/failed

### Key actions
- Run test issue
- Review latest comparison
- Open latest production issue
- Send test email

---

## 6.2 Issues

### Purpose
Provide a browsable library of generated issues across production and test.

### Main views
- list view
- optional grid/card view
- issue detail page

### Filters
- Production / Test
- Mode A / B1 / B2
- status: draft / reviewed / approved / sent / failed
- date range
- tags / run labels

### Issue list row/card metadata
- issue date
- mode used
- run tag
- environment: production or test
- send status
- recipient
- novelty warning level
- last updated time

### Issue detail page should include
- rendered HTML preview
- structured issue artifact view
- section-by-section story summary
- selected links/sources
- generation metadata
- issue status timeline
- duplication / novelty warnings
- actions:
  - clone as test run
  - compare with another issue
  - promote to production
  - send test email
  - archive

---

## 6.3 Runs / Experiments

### Purpose
This is the experimentation lab for generating and tracking ad hoc runs.

### Main tasks
- create a new run
- view run history
- inspect run outputs and logs
- compare modes
- keep production-safe separation from testing

### New run form
Should support:
- environment: test / production
- mode: A / B1 / B2
- run tag / experiment label
- refresh research toggle
- optional send-after-review toggle
- optional notes field

### Run history table
Each run should show:
- timestamp
- mode
- tag
- status
- duration
- artifacts created
- initiated by
- environment

### Run detail page should include
- run summary header
- log panel
- output artifact links
- HTML preview snapshot
- issue artifact snapshot
- research packet snapshot when applicable
- failure diagnostics when relevant

### Suggested UX tone
This screen should feel like a refined experiment workspace, not a developer console.

---

## 6.4 Review & Compare

### Purpose
This is the heart of the product.
It should let the operator compare runs side by side and make decisions.

### Core use cases
- compare Mode A vs B1 vs B2
- compare old B2 vs upgraded B2
- compare a test issue to the last production issue
- evaluate novelty / repeated stories
- choose a preferred run for promotion

### Required comparison capabilities
- compare 2 or 3 runs side by side
- compare final rendered newsletter previews
- compare section headlines by section
- compare issue-level metadata
- compare research packet summaries for B1/B2
- compare selected sources / links

### Must-have analysis modules
#### A. Scorecard panel
Show a reusable scorecard based on the persisted rubric:
- novelty vs recent issues
- section quality and fit
- kid readability
- source-to-story transformation
- pipeline quality
- structural/render quality

#### B. Story collision panel
Explicitly show:
- repeated URLs
- repeated events/themes
- likely cosmetic rewrites
- repeated evergreen facts
- sections with highest collision risk

#### C. Section diff panel
For each section:
- headline/title chosen by each mode
- key supporting sources
- which story cluster it appears to come from
- quick judgment tag: fresher / weaker / more generic / stronger fit

#### D. Recommendation panel
A compact summary card:
- recommended run
- why it wins
- blockers before promotion

### Key actions
- promote selected run to production
- mark reviewed
- add note
- export comparison snapshot

This screen should feel like the place where the operator makes editorial decisions.

---

## 6.5 Delivery

### Purpose
Manage send settings, scheduling, recipient details, and send history.

### Main content
- recipient email
- sender display name
- sender email/account status
- delivery timezone
- scheduled send day/time
- next scheduled send
- test send controls
- production send history

### Suggested modules
- **Delivery profile card**
- **Schedule editor**
- **Upcoming send timeline**
- **Send history table**
- **Manual send controls**

### Key actions
- save delivery settings
- send test email
- send selected issue now
- resend failed send

---

## 6.6 Content Setup

### Purpose
Manage the editorial configuration without editing YAML directly.

### Subsections
#### Child profile
- name
- age band
- location
- cultural context
- active interests

#### Sections
- reorder sections
- enable/disable sections
- edit titles/goals
- see section purpose summaries

#### Editorial settings
- reading level
- tone
- emoji usage
- source preferences

### UX expectations
- forms should be clean and not overwhelming
- changes should feel safe and previewable
- show clear distinction between editing content setup and editing system infrastructure

---

## 6.7 System / Providers

### Purpose
Configure the underlying generation pipeline and operator-level system settings.

### Main content
- current production default mode
- provider settings for:
  - research
  - ranker
  - synthesis
  - render
- separate test defaults vs production defaults
- cache behavior / refresh policy
- environment readiness checks

### Readiness/status panel
Show whether the system is configured for:
- Brave API
- Claude availability
- Gmail sending
- scheduler readiness

### Provider config needs
- choose production default mode
- choose test default mode
- configure ranker provider defaults
- surface B2 novelty/distinctness guidance state
- debug artifact retention toggle

---

## 7. Lifecycle and states

The UI should support the following lifecycle states:

- Draft
- Test generated
- Reviewed
- Approved
- Scheduled
- Sent
- Failed
- Archived

Production and test status should never be easy to confuse.
Use strong visual labeling and environment badges.

---

## 8. Required product features beyond the obvious

In addition to the baseline admin controls, include these features explicitly:

### 8.1 Promote tested run to production
A reviewed test run should be promotable to production without awkward manual copying.

### 8.2 Story collision risk panel
This should be a visible product feature, not buried in logs.

### 8.3 Recent issue headline history
A compact view of recent issue headlines should be available in comparison and review surfaces.

### 8.4 Experiment tags
Runs should support labels like:
- `mode-a`
- `mode-b1`
- `mode-b2`
- `mode-b2-v2`
- `novelty-test-1`

### 8.5 Recommendation card
The system should surface a recommendation such as:
- “Current recommended default: Mode B1”
- “B2 improved, but still trails on issue-level coherence”

This makes the tool feel opinionated and alive.

---

## 9. Visual design direction

### Design intent
The product should feel like:
- a premium editorial admin
- a calm AI-assisted workspace
- lightly warm, not sterile
- polished enough that it feels shippable

### Keywords
- calm
- editorial
- premium
- modern
- warm
- trustworthy
- crisp
- layered but uncluttered

### Avoid
- childish visual motifs
- cartoon UI
- dense enterprise dashboard chrome
- raw developer-tool aesthetic
- dark cyberpunk AI branding

### Suggested visual system
- soft neutral backgrounds
- subtle accent colors for modes/states
- clear cards and section groupings
- large readable headings
- comfortable spacing
- restrained icon use
- strong table/card hierarchy

### Mode color suggestions
- Mode A: cool blue
- Mode B1: green or teal
- Mode B2: purple or indigo
- Production: charcoal / neutral emphasis
- Test: lighter accent treatment

These should be subtle, not loud.

---

## 10. Components to design well

The UI should include polished versions of:
- sidebar navigation
- top context bar
- status cards
- issue cards
- run history table
- comparison columns
- scorecards
- risk badges
- timeline components
- empty states
- settings forms
- preview panels
- JSON/artifact inspector panels
- diff highlights

Important: JSON/artifact views should feel readable and useful, not like raw unstyled code dumps.

---

## 11. Accessibility and UX quality bar

The console should:
- be highly scannable in under 2 seconds per screen
- use strong typographic hierarchy
- make primary actions obvious
- avoid burying critical state
- support keyboard-friendly workflows where practical
- use explicit success/error/warning states
- preserve strong contrast and readability

---

## 12. Suggested initial screen set for design generation

Generate high-fidelity concepts for at least these screens:

1. **Dashboard**
2. **Issues library**
3. **Issue detail page**
4. **Run / experiment detail page**
5. **Review & Compare screen** with 3-way mode comparison
6. **Delivery settings screen**
7. **Content Setup screen**
8. **System / Providers settings screen**

If the tool supports multiple canvases, prioritize **Review & Compare** and **Dashboard** first.

---

## 13. Example seeded data ideas

Use realistic fake data such as:
- production issue sent last Friday
- three tagged test runs: `mode-a`, `mode-b1`, `mode-b2`
- upgraded B2 run: `mode-b2-v2`
- current recommended mode: `Mode B1`
- novelty warning: “2 sections overlap with recent issues”
- next send: Friday, 7:00 PM PT
- recipient: parent-controlled email inbox

This should help the tool produce more realistic UI states.

---

## 14. What success looks like

A successful design will make it immediately obvious that this product is for:
- generating issues
- comparing modes
- catching repetition
- managing configuration
- safely operating a weekly newsletter system

The most important design question is:

**Can the operator quickly understand what was generated, how it differs from alternatives, and whether it is safe and good enough to send?**

If yes, the design is on the right track.

---

## 15. Copy-ready prompt block for design tools

Use this block directly in Google Stitch or similar tools if needed:

> Design a polished desktop-first admin console for Sophie’s World, a kid-friendly weekly newsletter generation system. This is an operator/admin panel, not a consumer product. The UI should feel like a premium editorial studio combined with a lightweight AI content ops console. Core workflows: review generated issues, compare Mode A vs Mode B1 vs Mode B2 runs, inspect intermediate artifacts, catch repeated stories across recent issues, configure child/profile/editorial settings, manage delivery scheduling, and control system/provider defaults. Prioritize Review & Compare as a centerpiece. Include Dashboard, Issues library, Runs/Experiments, Review & Compare, Delivery, Content Setup, and System/Providers. Show production vs test separation clearly. Include novelty/risk panels, story collision warnings, run tags, recommendation cards, and promote-to-production flows. Use realistic fake data and make it feel like a real shippable product rather than a wireframe.
