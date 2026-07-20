---
name: checkin-monthly
description: A calm end-of-month step back. Use when Adam wants to review the month, or when a scheduled monthly nudge fires. Shows what changed in the task store (open vs done by category, small wins named), month-ahead calendar highlights (both Gmail accounts, kept separate), and undated open tasks to schedule or gently drop — then invites a short goals review and one reflection. Read-only; never sends.
---

# checkin-monthly

A once-a-month pull-back from the day-to-day: what shifted, what's coming, and — if Adam
wants — a light goals review. This is an **invitation, not an audit**. Skipping any part
costs nothing, and nothing here is framed as a backlog or a debt.

## Autonomy (ADR-001 §7 / autonomy.yaml)

- Gathering + summarising tasks/calendar → **autonomous** (read-only).
- Writing the goals review / reflection to the monthly note → **autonomous-but-flagged**.
- **Never** send mail, accept invites, modify a calendar, or delete a task here.

## Flow

1. **Gather** (deterministic):
   ```bash
   python3 skills/checkin-monthly/review.py
   ```
   This prints "what changed" (open vs done by category, plus small wins named), month-ahead
   calendar highlights (per account, kept separate), and open tasks with no due date. It also
   writes a monthly-note stub at `data/monthly/<YYYY-MM>.md`.

2. **Frame it warmly.** Present the review as a step back, not a report card ("Here's the
   month — want to look together?"). Lead with what changed and the small wins; keep the two
   accounts in **separate labelled sections**; a few lines per part, not a firehose.

3. **Goals review, gently.** Offer a short look at longer-arc goals — where did the month
   land, what's worth carrying forward. Offer a `monthly` prompt from
   `extracted/prompt_bank.json` (e.g. long-term projects, a skill to grow, free-time hopes)
   if it helps open the door. Keep it to what Adam wants to name — no forced goal-setting.

4. **Category cleanup, offered not imposed.** Walk the undated open tasks by category. For
   each, offer two easy doors: give it a date, or let it go. **Never force either.** If Adam
   wants to schedule one, note the date and (if he wants it tracked) offer `task-capture`. If
   he wants to drop one, that is a legitimate, healthy outcome — treat it as tidying, not failure.

5. **Ask ONE action-learning question** (skippable). Draw a single question from
   `extracted/action_learning_questions.json` — one only, never a batch. It's an offer with a
   zero-consequence skip; do not push if he passes.

6. **Record what he gives** (only what he gives):
   - Write the goals review into the `## Goals review` section of `data/monthly/<YYYY-MM>.md`.
   - Write any answer to the reflection/action-learning question into the `## Reflection` section.
   - Leave the machine-built `## What changed` snapshot as-is (it's the durable trace).

7. **Refresh the surface** (optional): `python3 build_pa_dashboard.py` so anything captured
   shows on `PA_DASHBOARD.html`.

8. **Close briefly.** Acknowledge the month, name a small win, stop. Never itemise undone
   things as debt — a month with loose ends is a normal month.

## Notes

- The PA is separate from CIDER. Legal deadlines may surface in the fairres calendar
  highlights; list them plainly, but do not pull case content into PA notes or act on it —
  that lives in the case tracks, not here.
- Completions aren't timestamped in the task store, so "small wins" reflects everything
  currently marked done, not strictly this-month's closes. Acknowledge them warmly; don't
  over-claim precision.
- If `review.py` returns empty sections (tool hiccup / offline), say so plainly and still
  offer the goals-review and reflection steps. A check-in should never hard-fail on a fetch.
