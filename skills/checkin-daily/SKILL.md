---
name: checkin-daily
description: A gentle morning start-of-day check-in. Use when Adam wants to look at today, or when a scheduled morning nudge fires. Shows today's calendar + a prioritised inbox glance (both Gmail accounts, kept separate) + due tasks, then invites up to three intentions. Read-only; never sends.
---

# checkin-daily

A calm morning framing: what's on today, what's worth a look, and — if Adam wants — up
to three intentions. This is an **invitation, not an audit**. Skipping any part costs
nothing.

## Autonomy (ADR-001 §7 / autonomy.yaml)

- Gathering + summarising calendar/inbox/tasks → **autonomous** (read-only).
- Writing intentions to the daily note / task store → **autonomous-but-flagged**.
- **Never** send mail, accept invites, or modify a calendar here.

## Flow

1. **Gather** (deterministic):
   ```bash
   python3 skills/checkin-daily/glance.py
   ```
   This prints today's calendar (per account), a prioritised inbox shortlist (per account,
   with noise counted + hidden), and tasks due today/overdue. It also writes a daily-note
   stub at `data/daily/<date>.md`.

   **Refresh Granola meetings** (do it here — the connector is agent-only, so the morning
   check-in is where the meeting cache stays fresh; the launchd builder can't reach it):
   call `mcp__claude_ai_Granola__list_meetings` (`time_range: last_30_days`), then persist with
   `lib.granola.write_cache([{ "id", "title", "date" }], generated=<today ISO>)`. This themes
   each meeting (case / medical / else work) into `data/granola_cache.json`, which the timeline
   and Nest read. If the connector is unavailable (headless/offline), skip silently — the
   previous cache stays valid. Meetings span all themes, but **do not** pull case meeting
   *content* into PA notes (see Notes).

2. **Frame it warmly.** Present the glance as an offer ("Here's today — want to look?").
   Refine the inbox shortlist with judgement: **lift genuinely important mail** — replies to
   Adam, real people, institutions/solicitors (e.g. Henry Williams) — and quietly demote any
   marketing that slipped the filter. Keep the two accounts in **separate labelled sections**;
   never blend them. One or two lines per section — a glance, not a firehose.

3. **Invite intentions.** Ask once, gently, for up to three things Adam wants to point at
   today. Offer a daily prompt from `extracted/prompt_bank.json` (a `daily` one) if it helps.
   If getting started feels like the sticky part, you may instead offer a single
   `activation` prompt from `extracted/reflection_prompts.json`. **One question either way,
   skippable, zero consequence.** Do not push if he skips.

4. **Record what he gives** (only what he gives):
   - Write the intentions into the `## Top 3 intentions` section of `data/daily/<date>.md`.
   - If an intention is clearly a task he wants tracked, offer to capture it via
     `task-capture` (`--source checkin`). Don't force it onto the task list.

5. **Refresh the surface** (optional): `python3 build_pa_dashboard.py` so anything captured
   shows on `PA_DASHBOARD.html`.

6. **Close briefly.** Acknowledge the start, name any small win, stop. Never itemise
   undone things as debt.

## Notes

- The PA is separate from CIDER. Legal mail *will* appear in the fairres inbox glance; list
  it plainly, but do not pull legal content into PA notes or act on it — that lives in the
  case tracks, not here.
- If `glance.py` returns empty sections (tool hiccup / offline), say so plainly and still
  offer the intentions step. A check-in should never hard-fail on a fetch.
