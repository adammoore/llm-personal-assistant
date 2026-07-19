# ADR-001 — Agent-Native Personal Assistant

- **Status:** Accepted (Phase 1 GATE passed 2026-07-19)
- **Date:** 2026-07-19
- **Owner:** Adam Vials Moore (adammoore)
- **Supersedes:** the 2024 FastAPI + React + OAuth "LLM Personal Assistant"

## Context

The 2024 app (see `INVENTORY.md`) was a FastAPI/React/SQLite stack with hand-rolled
Anthropic calls (`claude-2.0`), manual Google OAuth, and APScheduler. Its two most
valuable modules — comms triage and reporting — were never implemented (empty files).
The intent (an ADHD-supportive PA that initiates, checks in, and keeps calendar and
comms visible) is worth preserving; the stack is not. Modern tooling — Claude Code as
runtime, adam-local MCP, `gog`, `himalaya`, Granola, OpenClaw/Signal — makes the web
stack unnecessary. Phase 0 archived the intent (`extracted/`) and cleaned repo history.

## Decisions

1. **Runtime:** scheduled + on-demand Claude Code sessions. **No web server, no React,
   no bespoke OAuth.** Google via `gog`; email read/draft via `himalaya`/`gog`; meetings
   via Granola; nudges via OpenClaw/Signal.
2. **Task store — local files.** Markdown/JSON under `data/` (git-ignored, private). No
   database. `task-capture` appends; skills read/update. Legacy taxonomy carried forward
   (`Work/Personal/Health/Finance/Other`; add `category` as a first-class field, which the
   old SQLite model lacked).
3. **Primary surface — the PA's own standalone dashboard, decoupled from CIDER.**
   `build_pa_dashboard.py` renders `data/` → a self-contained `PA_DASHBOARD.html`
   (its own generator, own file/location). **CIDER is explicitly not the PA's surface** —
   it is one part of Adam's wider life, not the whole. The PA never writes into the CIDER
   dashboard or its regenerate path.
4. **Comms triage — both Gmail accounts, kept separate.** `fairresconman@gmail.com` and
   `moore.adam@gmail.com` are both in scope, but always rendered in **distinct, labelled
   sections**; threads are never blended. Work/personal boundary preserved. Never send
   unattended (`--gmail-no-send` / draft-only).
5. **iMessage — in scope.** Read the local `chat.db` on macOS. **Requires Full Disk Access
   granted to the terminal/Claude Code and explicit standing consent** (recorded here).
   Read-only; no message sending via iMessage.
6. **Nudges — Signal + calendar reminders.** `send_signal_alert` delivers one-tap-skippable
   invitations at cadence boundaries; check-ins also create calendar-event reminders as a
   secondary surface. Both channels carry a zero-consequence skip path.
7. **Autonomy — `autonomy.yaml` tiers** (replacing the legacy boolean toggle):
   - read / summarize → **autonomous**
   - create drafts, tasks, calendar *proposals* → **autonomous but flagged**
   - send messages, accept invites, modify calendars → **confirm required**
   - delete anything → **never autonomous**

## Repo strategy — legacy handling (DECIDED at GATE, 2026-07-19)

**Decision: preserve legacy code in `legacy/` on `main`** (Adam's call, overriding the
initial delete-and-archive recommendation — keeping it visible is preferred).

- Before restructuring, create tag **`v1-legacy`** and branch
  **`archive/2024-fastapi-react`** from the current clean HEAD (`3d19147`) and push both
  (belt-and-braces preservation).
- Then `git mv llm_personal_assistant/ legacy/` on `main` — the legacy app stays present
  and reconstructable (`npm install` regenerates the removed `node_modules`).
- **Note on the rewrite:** what is preserved is the **secret-clean** legacy app, not the
  original pre-rewrite history (which held live secrets + a 26-row personal DB). That
  original history exists only in the local backup bundle
  (`scratchpad/llm-pa-preRewrite-backup.bundle`) and is deliberately not re-published.

## Target root layout (post-Phase-2)

```
skills/            checkin-daily, checkin-weekly, checkin-monthly,
                   comms-triage, task-capture, quarterly-review   (one file each)
data/              markdown/JSON task store + check-in notes   (git-ignored, private)
ADR/               this + future ADRs
autonomy.yaml      the tiers above (enforced + documented)
build_pa_dashboard.py  data/ -> PA_DASHBOARD.html (separate from CIDER)
launchd/           daily/weekly/monthly job plists (Phase 3)
OVERHAUL_BRIEF.md  CHANGELOG.md  README.md (migration note -> v1-legacy tag)
extracted/         prompt bank, action-learning questions, taxonomy (Phase 0)
legacy/            the archived 2024 FastAPI/React app (preserved, not live)
```

## Build order (Phase 2 — one skill at a time, demo each before the next)

1. `task-capture` (unblocks the data store + dashboard)
2. `build_pa_dashboard.py` (the surface — validate rendering early)
3. `checkin-daily` (calendar + inbox glance, top-3 intentions)
4. `comms-triage` (both accounts, separate sections; draft-only)
5. `checkin-weekly` (one action-learning question + deadline horizon)
6. `checkin-monthly` (goals review, "what changed")
7. `quarterly-review` (assemble from daily notes, Granola, git, evidence)
Then Phase 3 (launchd + nudges), Phase 4 (decommission).

## Consequences

- **Positive:** no server/DB/OAuth to maintain; secrets surface shrinks to `gog`/keyring;
  every session leaves a durable markdown trace; PA cleanly separated from the legal case.
- **Costs / risks:** iMessage needs Full Disk Access (privacy surface; documented consent).
  `chat.db` schema can shift across macOS versions — isolate that read behind one module.
  Two-account comms needs disciplined labelling to keep the work/personal boundary.
  Credentials from the 2024 app were **not rotated** (Adam's decision) — accepted risk
  logged in `PHASE0_SECURITY_REPORT.md`.
- **Neurodivergent-first invariants (bind all skills):** invitations not demands; one
  question at a time; always a zero-consequence skip; small wins acknowledged, never
  itemised as debt.
