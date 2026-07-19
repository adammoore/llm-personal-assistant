# INVENTORY.md — Legacy LLM-PA Archaeology

**Date:** 2026-07-19 (Phase 0)
**Repo:** `github.com/adammoore/llm-personal-assistant` (branch `main`, HEAD `8b2f4cae`)
**All 12 commits date to 2024-09-02/03** — a ~2-day build, untouched since. Treat as an archaeology site.

## Shape

```
/                              root: EMPTY .gitignore (0B), EMPTY setup_project.sh (0B), .idea/ (JetBrains)
└── llm_personal_assistant/
    ├── backend/               FastAPI + async SQLAlchemy (SQLite)
    ├── frontend/              React 18 + MUI  (⚠ node_modules committed: 77,830 files / most of 118MB .git)
    ├── tests/                 3 test files
    ├── requirements.txt       pinned deps (fastapi 0.68, anthropic 0.2.6, pydantic 1.8 — all 2024-era)
    ├── README.md              setup/accessibility notes (Apache-2.0 claimed but no LICENSE file present)
    └── updates.txt            hand-kept changelog → CHANGELOG.md is its successor
```

## Backend — status per file

| File | Lines | Status | Notes |
|------|------:|--------|-------|
| `main.py` | 238 | ⚙️ live | FastAPI app, all routes. The spine. |
| `modules/llm_integration.py` | 203 | ⚙️ live | Parses LLM output into tasks/events; heavy debug logging. |
| `modules/prompt_system.py` | 86 | ⭐ **KEEP** | SQLAlchemy models + **`SAMPLE_PROMPTS`** (extracted). |
| `modules/task_manager.py` | 56 | ⚙️ live | CRUD; task model has **no category column** (category was UI-only). |
| `database.py` | 44 | ⚙️ live | async engine + `Task` model. |
| `scheduler.py` | 33 | ⚙️ live | APScheduler daily/weekly/monthly triggers → **concept survives as launchd jobs**. |
| `ai_autonomy.py` | 33 | 🔁 replace | Single boolean autonomy toggle → becomes `autonomy.yaml` tiers. |
| `config.py` | — | ⚙️ live | Pydantic settings from env (keys NOT hardcoded — good). |
| `llm/anthropic.py` | 63 | 🗑️ retire | Direct `requests` to Anthropic, model **`claude-2.0`** (brief said "v1 era" — it's claude-2.0). Superseded by Claude Code runtime. |
| `llm/openai.py` | 0 | 💀 dead | Empty stub. |
| `modules/communication.py` | 0 | 💀 dead | Empty — comms-triage goal was never implemented. |
| `modules/reporting.py` | 0 | 💀 dead | Empty — quarterly-review goal was never implemented. |
| `integrations/google_calendar.py` | 80 | 🔁 replace | Manual OAuth2 → replaced by `gog` CLI. Logic worth reading for behaviour parity. |
| `integrations/ticktick.py` | 185 | 🗑️ retire | Half-finished OAuth2 flow; creds from env only. Abandoned per brief. |
| `integrations/anydo.py` | 41 | 🗑️ retire | Abandoned stub. |
| `integrations/imessage.py` | 0 | 💀 dead | Empty — iMessage is an Open Decision. |
| `integrations/whatsapp.py` | 0 | 💀 dead | Empty — WhatsApp now via export analysis (adam-local `analyse_whatsapp`). |
| `backend/client_secret.json` | — | 🔴 SECRET | Live Google OAuth secret still at HEAD — see security report. |
| `backend/test.db` | — | 🔴 PII | 26 real personal task rows — see security report. |

## Frontend — status per file (`frontend/src/`)

| File | Status | Notes |
|------|--------|-------|
| `components/DailyPrompt.js` | ⭐ **KEEP** | Holds **`actionLearningQuestions`** (the "Twenty Questions" bank — 19 items, extracted). |
| `components/TaskList.js` | ⭐ **KEEP taxonomy** | `categories = [Work, Personal, Health, Finance, Other]` (extracted). |
| `components/AIAutonomyDialog.js` | 🔁 replace | The boolean autonomy toggle UI → `autonomy.yaml`. |
| `App.js`, `PromptSystem.js`, `CalendarEvents.js`, `AddTaskModal.js`, `TaskForm.js`, `GeneralSettings.js`, `index.js` | 🗑️ retire | MUI/React UI — retired wholesale (dashboard-only per brief). |
| `frontend/node_modules/**` | 🔴 purge | 77,830 tracked files; strip from history (security report §4). |

## What's worth keeping (→ `/extracted`)

1. **Prompt bank** — 10 cadence-keyed initiation prompts → `extracted/prompt_bank.json`.
2. **Action-learning questions** — 19-item reflection bank → `extracted/action_learning_questions.json`.
3. **Taxonomy** — task categories, cadence enum, legacy autonomy shape → `extracted/taxonomy.json`.
4. **Conceptual patterns to preserve (not code):** scheduler cadences (daily/weekly/monthly) → launchd; the neurodivergent framing; calendar-behaviour logic in `google_calendar.py` for parity when wiring `gog`.

## What's dead / never built (informs the rebuild scope)

- **`communication.py` and `reporting.py` are empty** — comms-triage and quarterly-review (brief goals #4 and #5) were *aspirations, never implemented*. The new build creates them from scratch, not a port.
- OpenAI, iMessage, WhatsApp integrations: empty stubs.
- Any.do / TickTick: abandoned or half-finished; drop.

## Mapping legacy → target (per brief goals)

| Brief goal | Legacy source | New home |
|-----------|---------------|----------|
| Initiation prompts | `SAMPLE_PROMPTS` | `checkin-daily/weekly/monthly` skills |
| Action-learning reflection | `actionLearningQuestions` | woven into weekly/monthly check-ins |
| Calendar awareness | `google_calendar.py` (manual OAuth) | `gog` CLI |
| Comms triage | *(empty stub)* | `comms-triage` skill (gog/himalaya) — net-new |
| Quarterly review | *(empty stub)* | `quarterly-review` skill — net-new |
| Scheduling | `scheduler.py` (APScheduler) | launchd jobs + Signal nudges |
| Autonomy | boolean toggle | `autonomy.yaml` tiers |
| Task store | SQLite `test.db` | plain markdown/JSON (Open Decision #1) |
