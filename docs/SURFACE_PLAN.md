# PA surface plan — for review (2026-08-13)

Generated from `python3 lib/surface_audit.py` (re-run any time). The audit checks every **input**
the PA reads and every **surface** it reaches Adam through, with an explicit **off-desktop** flag.

## Current state (from the audit)

**Surfaces (output) — all live** ✅
dashboard-desktop · **dashboard-tailnet (phone)** · **Signal nudges** · **Apple Reminders push
(20 tasks)** · **Apple Note (focus)** · situational brief. The mobile/tailnet + Reminders work just
closed the output gaps — the PA now reaches the phone/Watch/Siri, not just the desktop.

**Ingest (input) — 8/10 live** 🟢 mail · calendar · unified inbox · iMessage/SMS (WAL-fresh) ·
Reminders mirror · work (Enact CDP) · Granola · cider atoms.

**Gaps — 2 from the audit, both off-desktop INPUTS**, + 2 known workflow gaps:

| # | Gap | Why it matters | Effort |
|---|-----|----------------|--------|
| 1 | **Reminders completion is one-way** | You can now *see* tasks on the Watch/phone, but completing a "PA Tasks" reminder there doesn't mark the PA task done — they drift. The push is live; the return trip isn't. | **Low** |
| 2 | **WhatsApp not wired into ingest** (`wacli` restored) | Appointment reminders + real messages arrive on WhatsApp; the PA is blind to them (events, inbox). `detect_candidates` already takes any message list — it's a source-plug. | **Med** |
| 3 | **Signal is outbound-only** (no reply reading) | The PA nudges "reply *add*" to confirm an appointment, but can't read the reply — so confirmation only works via the dashboard button, not from the phone. | **Med-High** |
| 4 | **No low-disk guard** | Disk-full has silently corrupted state (the WAL watermark). An early warning would surface it loudly. Operational, not a surface. | **Low** |

## Proposed plan (priority order)

**P1 — Reminders two-way (close the completion round-trip).** When a "PA Tasks" reminder is
completed on the Watch/phone/Siri, mark the corresponding PA task done. Approach: `lib.remindpush`
gains a `pull()` — read completed reminders in "PA Tasks" (via `remindctl show --completed` or the
Core Data mirror, keyed by the `pa-task:<id>` url / the stored id map), `complete_task(id)` in the
PA store, drop from the push map. Run it alongside the daily-check-in sync and the `↗ Reminders`
button. *Makes the task surface genuinely two-way — the single highest-value small fix.*

**P2 — WhatsApp ingest.** Add WhatsApp to `_incoming_messages()` (event detection) and the unified
inbox. Approach: a small `lib.whatsapp.recent()` over `wacli messages --json` (throttled/cached like
Granola — daemons read a cache, a daily `wacli sync` + read writes it; NOT a live CLI per monitor
cycle, to avoid the store lock). Then appointment reminders + messages on WhatsApp flow into events
+ inbox for free.

**P3 — Signal reply-to-confirm.** Read inbound Signal (via OpenClaw) so a phone reply — "add",
"done 3", "capture: …" — acts: confirm a proposed appointment, complete a task, capture a task.
Approach: an OpenClaw inbound reader + a tiny command parser in the monitor; match "add" to the most
recent proposal. Higher effort (OpenClaw inbound plumbing + command grammar) — do after P1/P2.

**P4 — Low-disk guard.** Monitor checks free space each refresh; below a threshold (~5 GB) fire one
Signal nudge ("⚠ disk 4.2 GB free"). One small function; prevents silent state corruption.

## Not in scope (already done / external)
- Mobile responsiveness ✅ (verify on the phone at `…ts.net:8443`).
- The 20 GB cider-outputs disk reclaim → cider session (Round 3 handoff).

## Recommendation
Do **P1 + P4 now** (both Low effort, high safety/utility), then **P2** (WhatsApp) as the next real
input. **P3** (Signal two-way) is the biggest lift — schedule it deliberately. Re-run
`lib/surface_audit.py` after each to watch the gap count fall.
