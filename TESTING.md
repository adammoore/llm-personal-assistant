# Testing & evaluating the PA — phone + desktop

How to exercise every surface and judge whether it's actually helping. Run from the repo
root: `cd /Users/adamvialsmoore/llm-personal-assistant`.

## One command (start here)

```bash
python3 tests/smoke.py
```

Exercises the whole system safely — task store + schema, capture, focus (incl. `--energy`),
the unified activity stream (asserts soonest-first), the dashboard build, all prompt banks,
read-only calendar/inbox/OneDrive plumbing, and script syntax. **Nothing is sent, and task
writes go to a temp store — your real data and phone are untouched.** Prints `N passed, M
failed` and exits non-zero on any failure. The phone/Signal/visual bits it can't judge are
below.

## Desktop — the core, all working now

| Test | Command | Expect |
|------|---------|--------|
| Capture a task | `python3 skills/task-capture/capture.py "Test — buy milk"` | JSON printed, `mirrored_to_notes: true` |
| Store updated | `cat data/tasks.json` · `open data/tasks.md` | new task present in both |
| Dashboard | `python3 build_pa_dashboard.py` then `open data/PA_DASHBOARD.html` | calm, grouped, your task shows |
| Daily glance | `python3 skills/checkin-daily/glance.py` | calendar + prioritised inbox + due, both accounts separate |
| Weekly / monthly | `python3 skills/checkin-weekly/horizon.py` · `.../checkin-monthly/review.py` | 14-day horizon / what-changed |
| Comms triage | `python3 skills/comms-triage/triage.py --per-account 8` | per-account shortlist with ids |
| Quarterly draft | `python3 skills/quarterly-review/assemble.py` | digest to `data/reviews/<q>.md` |
| Work files | `python3 -c "import sys;sys.path.insert(0,'.');from lib.onedrive import render;print(render(days=14))"` | recent OneDrive files (metadata only) |
| A scheduled run (dry) | `DRY_RUN=1 bash schedule/run_checkin.sh daily` | preps note, refreshes PA Today, logs nudge (no send) |

Interactive (richer): open a Claude Code session here and run `/checkin-daily`, `/comms-triage`, etc.

## Phone — via Signal + iCloud-synced Notes

| Test | How | Expect |
|------|-----|--------|
| **Nudge arrives** | `bash schedule/nudge.sh "test nudge"` | Signal message on your phone |
| Scheduled nudge | `launchctl start com.adamvialsmoore.pa-checkin-daily` | the daily invitation on your phone |
| **PA Inbox note syncs** | capture on desktop → open Notes on phone | the task appears in `PA Inbox` |
| **PA Today note** | `python3 skills/checkin-daily/push_today.py` → Notes on phone | `PA Today` shows calendar + due + inbox counts |
| **Text the PA (newest)** | Signal-message yourself: `today` / `capture buy milk` / `what's due` | OpenClaw's Signal agent runs the skill and replies |

> The "text the PA" path is the newest and least-proven — the Signal agent now has access to
> the PA skills, but it may need a permission/profile tweak to run the helper scripts. If a
> reply doesn't come, tell me what it said and I'll adjust.

## End-to-end scenarios (the real test)

1. **Morning:** 07:30 nudge arrives → glance at the `PA Today` note on your phone → reply
   `today` to do the check-in → intentions get logged.
2. **On the go:** text `capture pick up prescription` → later on desktop, it's in the
   dashboard and `PA Inbox`.
3. **Monday:** the weekly nudge arrives → reply `week` → deadline horizon + one reflection.

## What "good" looks like (evaluation criteria)

- **Invitational, not nagging** — nudges read as offers; ignoring one costs nothing.
- **Consistent** — a capture from any surface shows up on every surface, no drift.
- **A glance, not a firehose** — inbox is prioritised; the dashboard/notes stay calm.
- **Boundaries held** — no case/medical/legal content leaks into PA outputs; the two Gmail
  accounts stay in separate sections.
- **On time** — daily 07:30, weekly Mon 08:00, monthly 1st 09:00 fire as set.
- **Low activation energy** — one command or one Signal tap starts anything.

## Quick health checks

```bash
launchctl list | grep -E 'pa-checkin|signal-cli-daemon'   # jobs + daemon loaded
lsof -iTCP:8080 -sTCP:LISTEN                               # signal daemon serving
tail -n 20 data/logs/checkin-daily.log                    # last runs
```
