---
name: focus
description: Collapse everything to one thing. Use when Adam wants to concentrate on a single theme/project ("focus on Enact", "just the Case stuff") or on what's high-priority. Shows that theme's tasks plus related dates and messages, and can push the view to the phone (synced note + Signal). The deep-focus complement to the central-overview dashboard.
---

# focus

The overview shows everything; **focus** shows one thing. Give it a theme (project tag) or a
priority and it pulls together that thread — tasks first, then the upcoming dates and
messages that mention it — so Adam can go deep without the rest of the world in view.

## Autonomy

- Gathering the focused view → **autonomous** (read-only).
- `--push-note` (write the synced "Focus" Apple Note) → **autonomous-flagged**.
- `--signal` (short summary) → pre-authorized nudge.
- Never sends mail, never writes into CIDER.

## How to run

```bash
python3 skills/focus/focus.py <Theme>            # e.g. Enact, Case, House
python3 skills/focus/focus.py --priority high    # everything high-priority, across themes
python3 skills/focus/focus.py Case --push-note --signal
```

- **Theme** matches a task's `theme` tag (or a mention in its title). Dates/messages have no
  theme, so they're matched by the theme keyword — good enough to surface the obvious ones.
- `--push-note` writes a `Focus — <theme>` Apple Note that iCloud-syncs to the phone.
- `--signal` sends a one-line summary (task count, top item) to Signal.

## Setting up themes

Themes are just tags on tasks — capture with `--theme`:
`python3 skills/task-capture/capture.py "Ship wireframes" --theme Enact --priority high`.
There's no fixed list; use whatever areas matter (Enact, Case, House, Health…). Suggest a
theme when capturing if one is obvious, but never force it.

## Boundary

Focus is part of the central hub, so it **surfaces** case-relevant tasks/dates/messages for
visibility (e.g. a `Case` focus is fine). It still never drafts legal content, applies
legal-team-only analytical labels, or touches CIDER's data — that deep-focus space is
separate by design.
