---
name: monitor
description: The always-on monitoring loop (ADR-002) — the constant-companion layer. Not invoked by hand; it runs as a launchd daemon. Use this doc to check its status, tune it, or explain how proactive nudges work.
---

# monitor

The dynamic layer that makes the PA a *companion that watches* rather than an assistant you
visit. A persistent loop (`monitor.py`, run by the `com.adamvialsmoore.pa-monitor` launch
agent) every ~2.5 min does cheap deterministic reads, diffs against `data/state.json`, and
reacts to **genuinely new** events:

- new worth-a-look **mail** → "✉ sender: subject"
- an **imminent meeting** (~15 min) → "📅 title in ~N min"
- a task that flips to **due-today/overdue** → "⏰ task — due today"
- keeps `PA_DASHBOARD.html` + the `PA Today` note fresh (≤ every 15 min)

Watching is **LLM-free**; nudges reuse `schedule/nudge.sh`. It's tuned **chatty** (Adam would
rather ignore a nudge than miss something), and leans on **dedup** — the *same* event is
nudged once, ever — so it never nags.

## Manage

```bash
launchctl list | grep pa-monitor          # running?
tail -f /tmp/pa-monitor.log               # what it's doing
launchctl unload ~/Library/LaunchAgents/com.adamvialsmoore.pa-monitor.plist   # stop
```

Test safely without sending or looping:
```bash
python3 skills/monitor/monitor.py --once --dry --state /tmp/s.json    # one pass, no sends
```

## Tune

Edit the `monitor:` block in `autonomy.yaml` (poll interval, imminent window, rate caps,
which watchers are on), then reload the launch agent. Dedup is always on and not
configurable — it's what keeps a 24/7 companion from becoming a nag.

## Boundaries

Read-only watching + pre-authorized nudges only. The loop never sends mail, drafts, mutates
Google/CIDER, or runs the LLM. On any single-cycle error it logs and continues.
