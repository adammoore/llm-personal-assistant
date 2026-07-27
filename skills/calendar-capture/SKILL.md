---
name: calendar-capture
description: Create the calendar events Adam has confirmed from message-detected appointments. Use when Adam says "add my proposed appointments / add that to my calendar", when he's clicked ＋add on the dashboard's Proposed appointments card, or as a step in the daily check-in. Reads the confirmed queue and writes each to fairresconman via the Calendar connector; confirm-gated by design.
---

# calendar-capture

Phase 3 of event capture. The monitor DETECTS appointment reminders in incoming messages and
PROPOSES them (Signal nudge + the dashboard's 📅 Proposed appointments card). When Adam **confirms**
one — clicks **＋ add**, or tells you to add it — this skill creates the real calendar event.

Why a skill (not the daemon): `gog` can read the calendar but not create events, so creation goes
through the **Google Calendar connector**, which only an agent can call. The daemon just queues
Adam's confirmation (`status: confirmed`); this skill does the write.

## Autonomy / boundary
- `autonomy.yaml`: `modify_calendar` is **confirm-required**. The `confirmed` status IS Adam's
  confirmation, so create the queued events **without re-asking** — but show him what you created.
- Default calendar: **fairresconman** (Adam's stated target). If an event is obviously personal,
  you may ask which calendar; otherwise use fairres.
- These are appointments (personal/work) — not case content; no wall concern. Never invent details:
  only what the message actually said.

## Flow

1. **Read the confirmed queue** (nothing to do if empty):
   ```bash
   python3 -c "import json,sys; sys.path.insert(0,'.'); from lib.calevent import pending, event_fields; \
     print(json.dumps([{**event_fields(p),'key':p['key']} for p in pending('confirmed')], indent=1))"
   ```
   Each row gives `{key, title, start (ISO), end, all_day, location, description, account}`.

2. **Create each event** via the Calendar connector. Discover the tool by keyword (the connector
   prefix varies — `mcp__claude_ai_Google_Calendar__create_event` / bare); never hardcode a prefix.
   Map fields: `summary`=title, timed events use `start`/`end` datetimes (Europe/London), all-day
   events use the date; set `location` and `description`; target the **fairresconman** calendar.
   Sanity-check the parsed date/time against the `description` (the raw message) before creating —
   if the date looks wrong or ambiguous, ask Adam rather than guess.

3. **Mark it done** so it leaves the queue and won't be re-created:
   ```bash
   python3 -c "import sys; sys.path.insert(0,'.'); from lib.calevent import set_status; set_status('<key>','added')"
   ```

4. **Confirm briefly** — one line per event created ("Added *Appointment: ADHD Post Diagnostic* —
   Mon 3 Aug 13:30 to fairres"), and offer to undo (delete) if any looks wrong. Then rebuild the
   dashboard so the card clears: `python3 build_pa_dashboard.py`.

## Notes
- If the connector is unavailable (offline/headless), say so and leave the items `confirmed` — they
  stay queued for next time; never fail silently.
- One event may be genuinely ambiguous ("Friday at 3" with no date near a month boundary). Prefer
  asking over creating a wrong entry — a wrong calendar event is worse than a delayed one.
