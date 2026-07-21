# ADR-002 — Dynamic Monitoring Layer (the constant companion)

- **Status:** Proposed (awaiting GATE sign-off)
- **Date:** 2026-07-21
- **Owner:** Adam Vials Moore
- **Extends:** ADR-001

## Context

ADR-001 delivered a capable PA, but its interaction model is **clock-driven, on-demand, and
stateless**: it acts at fixed times (07:30 / Mon / 1st) or when Adam asks, and each run is a
fresh pull with no memory of what changed. That is an *assistant you visit*, not the
**constant companion** the ADHD-PA spec calls for — something that *continuously monitors and
processes* and reacts *when things happen*.

Two properties are missing: **continuous event-driven monitoring** and **statefulness**
(knowing what's new since last look). Note the always-on substrate already exists — the
signal-cli daemon and OpenClaw gateway run continuously, and OpenClaw inbound is already
event-driven — we just haven't built the monitoring loop on top.

## Decision

Add one purposeful **monitor daemon**: a persistent loop (launchd `KeepAlive`) that every
~2–3 minutes does **cheap, deterministic reads**, **diffs against saved state**, and reacts
only to *changes*. The watching is LLM-free; skills/LLM fire only when Adam engages (via
OpenClaw) — so it is *constantly monitoring without constantly costing*.

This intentionally revises ADR-001's "no daemon" stance: reality already runs daemons
(signal-cli, OpenClaw); this adds a single, well-scoped one for monitoring.

## What it watches → how it reacts (proactivity: "react to important events")

| Watcher | Trigger (vs. saved state) | Reaction |
|---------|---------------------------|----------|
| **mail** | a new *worth-a-look* message (real person/solicitor) not seen before, per account | nudge: "`<sender>` emailed re `<subject>`" |
| **calendar** | an event starting within N min (default 15) not yet reminded | nudge: "`<title>` in ~15 min" |
| **deadline** | an open task flips to due-today or overdue since last check | gentle nudge: "`<task>` is due today" |
| **surfaces** | every M minutes regardless | refresh `PA_DASHBOARD.html` + `PA Today` note |
| **capture** | inbound Signal (already handled by OpenClaw) | — (documented, not duplicated) |

## Architecture

- **`skills/monitor/monitor.py`** — the loop: poll each watcher → emit events → react →
  persist state → sleep(interval). Idempotent across restarts (reads state on boot).
- **State** — `data/state.json` (git-ignored): last-seen mail id per account, reminded event
  ids, per-task due-state, and a nudge ledger (event-key → last-sent time) for dedup.
- **Reactions** — reuse `schedule/nudge.sh` (Signal) and the existing dashboard/PA-Today
  renderers. Watchers are cheap `lib.comms` / `lib.taskstore` reads; **no LLM in the loop**.
- **Launch agent** — `com.adamvialsmoore.pa-monitor` (`RunAtLoad` + `KeepAlive`), like the
  signal-cli daemon.

## Anti-fatigue (critical, since quiet hours = anytime)

A companion that nags is worse than none. Even running 24/7:
- **Dedup** — every event has a stable key; it is nudged **once**, ever (tracked in state).
- **Rate-limit** — a minimum gap between nudges (default 90s) and a per-hour cap (default 6);
  excess events **coalesce** into one "a few things need you" nudge.
- **Invitational** — every nudge is skippable, no follow-up, no debt framing (ADR-001 ethos).
- **Config** in `autonomy.yaml` (`monitor:` block): poll interval, imminent-window, rate caps,
  and which watchers are on — so Adam tunes it without code.

## Autonomy

Monitoring reads → **autonomous**. Nudges → the existing **pre-authorized** nudge exception.
The loop **never** sends mail, drafts, or mutates Google/CIDER. No new outbound surface.

## Consequences

- **Positive:** the PA becomes reactive and continuous — surfaces things as they happen,
  remembers what's new, stays a live companion. Cheap (deterministic loop; LLM only on
  engagement).
- **Costs / risks:** a new always-on process to keep healthy (KeepAlive + logs); nudge
  fatigue is the real danger — mitigated by dedup/rate-limit/coalesce above, tunable in
  config. Sensitive (case) items will surface — intended, per the central-overview reframe;
  it's Adam's private device.
- **Reversible:** `launchctl unload` stops it; the scheduled/on-demand system keeps working.

## Build plan (after GATE)

1. `lib/state.py` — load/save `data/state.json` + a dedup/rate-limit ledger helper.
2. `skills/monitor/monitor.py` — watchers (mail/calendar/deadline) + reaction loop.
3. `autonomy.yaml` `monitor:` config block.
4. `com.adamvialsmoore.pa-monitor` launch agent (+ repo template) + SIGNAL-style docs.
5. `tests/smoke.py` coverage for watchers/state (dry, no sends).
