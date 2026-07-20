# schedule/ — cadence, nudges, and how they run

Phase 3 of the overhaul: the check-ins run themselves and invite Adam. Nothing here is a
demand — every nudge is skippable by simply ignoring it.

## How it works

```
launchd (StartCalendarInterval)
   └─> run_checkin.sh <daily|weekly|monthly>
         1. runs the deterministic prep (glance/horizon/review) → refreshes the durable note
         2. sends ONE skippable Signal invitation via nudge.sh
   (the interactive check-in happens later, only if Adam engages — ignoring = skip)
```

The scheduled job never runs the *interactive* check-in. It preps the note and invites.
Adam replies (routed via OpenClaw) to start the real check-in in a Claude session.

## Cadence (chosen 2026-07)

| Cadence | When | launchd plist |
|---------|------|---------------|
| daily   | 07:30 every day | `com.adamvialsmoore.pa-checkin-daily.plist` |
| weekly  | 08:00 Mondays | `com.adamvialsmoore.pa-checkin-weekly.plist` |
| monthly | 09:00 on the 1st | `com.adamvialsmoore.pa-checkin-monthly.plist` |

## Install (run these yourself when ready)

```bash
cp schedule/launchagents/com.adamvialsmoore.pa-checkin-*.plist ~/Library/LaunchAgents/
for c in daily weekly monthly; do
  launchctl load ~/Library/LaunchAgents/com.adamvialsmoore.pa-checkin-$c.plist
done
launchctl list | grep pa-checkin   # verify
```

There is **no `RunAtLoad`**, so loading them never fires an immediate nudge. Test one
on demand with: `launchctl start com.adamvialsmoore.pa-checkin-daily`.

## Signal nudges — safe by default

`nudge.sh` sends nothing until configured. Copy the template and set ONE backend:

```bash
cp schedule/nudge.env.example schedule/nudge.env   # nudge.env is git-ignored
```

- **Option A (recommended):** `NUDGE_CMD` — any command; the text arrives in
  `$NUDGE_MESSAGE`. Point it at your OpenClaw / `send_signal_alert` wrapper.
- **Option B:** `SIGNAL_FROM` + `SIGNAL_TO` — sends via `signal-cli`.

Verify without scheduling: `DRY_RUN=1 bash schedule/run_checkin.sh daily` (preps + logs the
nudge text, sends nothing). Logs: `data/logs/checkin-<cadence>.log` and `/tmp/pa-checkin-*.log`.

## Calendar reminders (second channel)

The chosen nudge behaviour is **Signal + calendar reminders**. The calendar reminders are
three recurring events (Daily 07:30, Weekly Mon 08:00, Monthly 1st 09:00) on the personal
calendar. Creating them mutates the calendar (`modify_calendar` = confirm-required), so they
are **not** created automatically — ask Claude to add them, or create them by hand. They are
purely a visible cue; the launchd jobs above are what actually run the check-ins.
