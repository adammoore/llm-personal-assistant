# Personal Assistant (agent-native)

An ADHD-supportive personal assistant that **initiates, checks in, and keeps your calendar
and communications visible** — rebuilt as a set of Claude Code skills over the existing
adam-local / `gog` / `himalaya` / Granola / Signal tooling. No web server, no database,
no bespoke OAuth.

> **Neurodivergent-first, PDA-aware:** invitations, not demands. One question at a time.
> Always a zero-consequence skip. Small wins acknowledged, never itemised as debt.

## What it does

- **Daily / weekly / monthly check-ins** — start-of-period framing, top-3 intentions, a
  calendar + inbox glance, one action-learning reflection question (weekly/monthly).
- **Comms triage** — summarises both Gmail accounts (kept in separate, labelled sections),
  proposes draft replies. Never sends unattended.
- **Task capture** — friction-free add from chat or Signal into a local task store.
- **Quarterly review** — assembles a draft report from real activity (daily notes, Granola
  meetings, git history, evidence store).
- **Nudges** — Signal invitations + calendar reminders at cadence boundaries, each
  skippable in one tap.

## Quick start

No server to start — everything runs through Claude Code. From this directory:

- **Capture a task:** `python3 skills/task-capture/capture.py "Call the dentist"`
- **Look at today:** run `/checkin-daily` in a Claude session (or `python3 skills/checkin-daily/glance.py` for just the glance)
- **See your dashboard:** `python3 build_pa_dashboard.py` → open `data/PA_DASHBOARD.html`
- **More:** `/comms-triage` · `/checkin-weekly` · `/checkin-monthly` · `/quarterly-review`

Scheduled nudges (daily 07:30, weekly Mon 08:00, monthly 1st 09:00) run automatically once
installed — see [`schedule/README.md`](schedule/README.md).

## Layout

| Path | What |
|------|------|
| `skills/` | one skill per capability (built + demoed one at a time) |
| `data/` | local markdown/JSON task store + check-in notes (git-ignored, private) |
| `build_pa_dashboard.py` | renders `data/` → `PA_DASHBOARD.html` (this PA's own surface) |
| `autonomy.yaml` | what the PA may do autonomously vs. confirm — enforced by every skill |
| `ADR/` | architecture decision records (start with `ADR-001`) |
| `extracted/` | prompt bank + action-learning questions + taxonomy salvaged from v1 |
| `legacy/` | the archived 2024 FastAPI/React app — preserved, **not** live |
| `CHANGELOG.md` | migration + change log (successor to the old `updates.txt`) |

## The PA is not CIDER

This assistant is deliberately **separate from the CIDER situation dashboard**. CIDER is one
part of a wider life; the PA has its own surface (`PA_DASHBOARD.html`) and never writes into
CIDER's data or regenerate path.

## Migration note

This repo previously held a FastAPI + React + SQLite app (2024). That app is preserved two
ways: in the [`legacy/`](legacy/) directory on `main`, and at the **`v1-legacy`** git tag /
`archive/2024-fastapi-react` branch. History was rewritten in 2026-07 to remove committed
secrets and a large vendored `node_modules`; clones from before that date will diverge.

To run the legacy app, see [`legacy/README.md`](legacy/README.md) (run `npm install` in
`legacy/frontend` first — vendored modules were removed from history).

## Status

Agent-native rebuild in progress — see `CHANGELOG.md` and `ADR/ADR-001-agent-native-pa.md`.
