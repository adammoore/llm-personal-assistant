---
name: checkin-weekly
description: A gentle weekly step-back check-in. Use when Adam wants to look at the week ahead, or when a scheduled weekly nudge fires. Shows a two-week deadline horizon (both Gmail calendars, kept separate) + a loose-thread sweep of overdue/due-this-week tasks, then invites ONE reflection. Read-only; never sends or touches the calendar.
---

# checkin-weekly

A calm weekly framing: what's on the horizon, which threads have quietly gone loose, and —
if Adam wants — one small reflection. This is an **invitation, not an audit**. Skipping any
part costs nothing, and undone work is never itemised as debt.

## Autonomy (ADR-001 §7 / autonomy.yaml)

- Gathering + summarising calendar/tasks → **autonomous** (read-only).
- Writing the reflection / picked-up threads to the weekly note → **autonomous-but-flagged**.
- **Never** send mail, accept invites, or modify a calendar here.

## Flow

1. **Gather** (deterministic):
   ```bash
   python3 skills/checkin-weekly/horizon.py
   ```
   This prints a 14-day deadline horizon (per account, kept separate) and a loose-thread
   sweep — open tasks that are overdue or due by the end of this week, grouped by category.
   It also writes a weekly-note stub at `data/weekly/<YYYY-Www>.md`.

2. **Frame it warmly.** Present the horizon as an offer ("Here's the shape of the week —
   want to look?"). Keep the two accounts in **separate labelled sections**; never blend
   them. Lift anything genuinely time-sensitive; a couple of lines per section — a horizon,
   not a firehose. The loose-thread sweep is a gentle "these are still hanging", not a
   reckoning.

3. **Ask exactly ONE action-learning question.** Choose a single question from
   `extracted/action_learning_questions.json` (the "Twenty Questions" bank) — one per
   session, never a batch. Frame it as an offer he can take, defer, or skip with zero
   consequence (PDA-aware). If a `weekly` prompt from `extracted/prompt_bank.json` fits the
   week better (deadlines, procrastination, self-care, dependencies), you may offer that
   instead. A single `reflection` or `reframe` prompt from
   `extracted/reflection_prompts.json` is also fair game if a gentler step-back fits — but
   still only one, still skippable.

4. **Record what he gives** (only what he gives):
   - Write his answer into the `## Reflection` section of `data/weekly/<YYYY-Www>.md`.
   - Note any thread he chooses to pick back up under `## Loose threads picked up`.
   - If a picked-up thread is clearly a task he wants tracked, offer to capture it via
     `task-capture` (`--source checkin`). Don't force it onto the task list.

5. **Refresh the surface** (optional): `python3 build_pa_dashboard.py` so anything captured
   shows on `PA_DASHBOARD.html`.

6. **Close briefly.** Acknowledge the step-back, name any small win, stop. Never itemise
   the undone threads as debt — a loose thread is a thread, not a failure.

## Notes

- The PA is separate from CIDER. Legal deadlines *will* appear on the fairres calendar
  horizon; list them plainly, but do not pull legal content into PA notes or act on it — that
  lives in the case tracks, not here.
- If `horizon.py` returns empty sections (tool hiccup / offline), say so plainly and still
  offer the reflection step. A check-in should never hard-fail on a fetch.
