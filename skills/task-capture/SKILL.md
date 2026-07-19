---
name: task-capture
description: Friction-free task capture. Use when Adam wants to add a task / to-do / reminder from chat or Signal — "add a task", "remind me to…", "capture:", or any dumped intention that should not be lost. Appends to the local task store; never interrogates.
---

# task-capture

Capture a task into the local store with the least possible friction. This is a
low-activation-energy path: the point is that a half-formed intention gets caught, not
that it is perfectly classified.

## Principles (ADR-001, neurodivergent-first)

- **Never interrogate.** Do not ask for a category, due date, or details. Infer what you
  can; default the rest. A captured-but-vague task beats a lost one.
- **One-shot.** Capture, confirm in one line, stop. No follow-up questions unless Adam adds more.
- **Autonomy tier:** `create_task` is *autonomous-but-flagged* — do it immediately, then
  surface the one-line confirmation. No permission needed.

## How to run

1. Extract from Adam's words:
   - **title** — a clean imperative ("Call the dentist"), stripped of "remind me to" etc.
   - **category** — only if obvious, one of Work / Personal / Health / Finance / Other.
     If not obvious, omit (defaults to Other). Do **not** ask.
   - **due** — only if a date is stated or clearly implied ("Friday", "next week" → resolve
     to ISO `YYYY-MM-DD`). If none, omit.
   - **source** — `signal` if the request arrived via Signal, else `chat`.
2. Call the helper:
   ```bash
   python3 skills/task-capture/capture.py "<title>" [--category <C>] [--due <YYYY-MM-DD>] [--source <s>]
   ```
3. Confirm in one line, acknowledging the small win — e.g.
   `✓ Captured: Call the dentist (Health, due Fri 25 Jul) — #7`. Then stop.

## Store

Canonical: `data/tasks.json` (a JSON array, git-ignored/private). The helper owns the
format, generates the id, and writes atomically. Other skills (`checkin-*`,
`build_pa_dashboard.py`) read this file. Never hand-edit it mid-session — go through the helper.

## Multiple tasks

If Adam dumps several intentions at once, call the helper once per task. Confirm them as a
short bulleted list of small wins, not a debt ledger.
