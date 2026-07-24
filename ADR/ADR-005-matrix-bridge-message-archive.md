# ADR-005 — WhatsApp & Signal archive via a Matrix bridge

- **Status:** Proposed (plan — awaiting go-ahead)
- **Date:** 2026-07-24
- **Extends:** the unified comms inbox (`lib/inbox.py`), ADR-002 (monitor), the OpenClaw/Signal + WhatsApp capture work
- **Trigger:** open-source app survey (2026-07-24) — Beeper/Texts.com solve exactly the gap we hit

---

## Problem

The unified inbox (`lib/inbox.py`) is limited to **structured, readable venues**: the two Gmail
accounts and iMessage (`chat.db`). **WhatsApp and Signal history is not readable**:

- **OpenClaw relays, it does not archive.** Inbound WhatsApp/Signal messages are handed to the
  agent and live only in ephemeral session transcripts. There is no message store to query.
- **signal-cli** exposes a single live receive stream (OpenClaw owns it) — no history.
- So the two channels Adam most wanted in the inbox contribute nothing to it.

The survey found the whole "unified inbox" category (Beeper, Texts.com) is built on **Matrix
bridges** — the exact open-source technology that turns these relay-only channels into a
**queryable local archive**.

## The insight

**Beeper = a Matrix homeserver + `mautrix-*` bridges.** Each bridge logs into the service as a
*linked device* (same model as WhatsApp Web / Signal's linked devices), **backfills history**,
and mirrors every conversation into Matrix rooms held in a local database. Point the PA at that
database (or the Matrix API) and WhatsApp + Signal become first-class inbox venues — read-only,
structured, historical — just like iMessage's `chat.db`.

## Architecture

```
  WhatsApp ──▶ mautrix-whatsapp ─┐
  Signal   ──▶ mautrix-signal   ─┼──▶ Matrix homeserver ──▶ local DB (SQLite)
                                 │      (conduwuit)              │
                                 └──────────────────────────────┘
                                                                 ▼
                                              lib/matrix.py  (read-only reader)
                                                                 ▼
                                              lib/inbox.py  (new venues: WhatsApp, Signal)
```

**Component choices (fit the PA's local, low-ceremony ethos):**

| Layer | Pick | Why |
|-------|------|-----|
| Homeserver | **conduwuit** (Rust, single binary, SQLite) | Lightest option — no Postgres, no Python/Synapse stack. Personal-scale. (Dendrite is a Go alternative; Synapse is overkill.) |
| WhatsApp bridge | **mautrix-whatsapp** (Go, `whatsmeow`) | Mature; links by QR; backfills history. WhatsApp allows **4 linked devices** → coexists with the OpenClaw link. |
| Signal bridge | **mautrix-signal** (Go) | Links as another Signal device; coexists with signal-cli (Signal allows multiple linked devices). |
| PA reader | **`lib/matrix.py`** | Read the homeserver's SQLite room/event tables (like `lib/imessage.py` reads `chat.db`), OR query the Matrix client-server API as a bot user. DB read is simplest + deterministic. |

## How the PA consumes it

Mirror the iMessage pattern exactly:

1. `lib/matrix.py` — read-only reader over the conduwuit SQLite store (or C-S API). Returns
   recent messages per room: `{venue, who, text, date, unread}`, with WhatsApp/Signal derived
   from the bridge/room.
2. `lib/inbox.py` — add **WhatsApp** and **Signal** as venues in `unified()`; the existing
   context-derivation (`_ctx_for`) applies unchanged (case people/refs → legal, etc.).
3. Monitor's `_refresh_surfaces` already refreshes the inbox cache — the new venues ride along.

**Bonus — deterministic capture.** Once WhatsApp/Signal history is locally readable, phone
*capture* can work the iMessage way (prefix-detect a self-message → task), **without** depending
on the OpenClaw LLM agent's choices. That removes the fragile agent-in-the-loop for capture and
makes it instant + free.

## Coexistence with the current stack

- **No conflict with OpenClaw.** mautrix-whatsapp/signal register as *additional* linked devices;
  OpenClaw's WhatsApp link and signal-cli daemon keep working. Outbound nudges stay on OpenClaw.
- Over time, if the Matrix archive proves reliable, the WhatsApp→Reminders capture hack could be
  retired in favour of deterministic Matrix-based capture — but nothing forces that.

## Fit vs. tension with the ethos

- **Tension:** this adds a **self-hosted server + two bridge daemons** — more infra than the
  local-file store. It is, however, in the same class as the *already-running* OpenClaw gateway
  and OneDrive/signal-cli — a sanctioned local service, not a cloud dependency. All data stays on
  the Mac.
- **Fit:** it's the *only* way to get WhatsApp/Signal **history** (not just live relay), and it's
  the proven, open-source, actively-maintained path (it is literally what Beeper runs).

## Risks

- **Operational weight:** 3 new long-running processes (homeserver + 2 bridges) under launchd,
  each with config + its own SQLite. More to keep alive/monitor.
- **Linking friction:** one QR scan (WhatsApp) + one device-link (Signal), like the OpenClaw
  flow — and re-link if a session drops.
- **ToS grey area:** unofficial linked-device bridges (same as Beeper/Texts) — acceptable for
  personal single-user archival; do not automate outbound at scale.
- **Backfill limits:** bridges backfill recent history, not necessarily the full lifetime of a
  chat (WhatsApp especially). Forward-fill from link-time is reliable.
- **Disk:** homeserver + media store grows; cap media backfill (text-only is fine for the inbox).

## Options

- **A. Full bridge stack (recommended for the goal).** conduwuit + mautrix-whatsapp +
  mautrix-signal + `lib/matrix.py` reader → WhatsApp & Signal in the unified inbox, plus optional
  deterministic capture.
- **B. WhatsApp only, first.** Just conduwuit + mautrix-whatsapp — smaller first step, proves the
  pattern on the channel Adam actively uses, before adding Signal.
- **C. Don't self-host — use Beeper/Texts as the client.** Run Beeper (Automattic) as the human
  UI, skip the PA integration. Loses the "one coordinated PA view"; note Beeper *dropped iMessage*.
- **D. Defer.** Keep the inbox at mail + iMessage; revisit if the WhatsApp/Signal gap bites.

**Recommendation:** **B → A.** Stand up conduwuit + **mautrix-whatsapp** first (WhatsApp is the
live pain point), ship `lib/matrix.py` + the WhatsApp inbox venue, confirm the archive + reader
are solid, then add **mautrix-signal**. Incremental, each step independently useful, and it
finally closes the biggest known gap in the unified inbox.

## Build sketch (when green-lit)

1. **Homeserver:** install conduwuit (single binary), minimal config, launchd agent, loopback-only.
2. **mautrix-whatsapp:** config against conduwuit; register the appservice; start; **scan QR** to
   link (4th device); let it backfill.
3. **`lib/matrix.py`:** read-only reader over conduwuit's SQLite (rooms/events), decode message
   events → `{venue:"WhatsApp", who, text, date}`. Model on `lib/imessage.py`.
4. **`lib/inbox.py`:** add the WhatsApp venue; context derivation unchanged; refresh via monitor.
5. **Verify** WhatsApp threads appear in the Inbox card under the right contexts; then repeat 2–4
   for **mautrix-signal**.
6. **(Optional)** deterministic WhatsApp/Signal capture (prefix self-message → task), retiring the
   agent-in-the-loop capture if it proves better.

**Effort:** comparable to the OpenClaw/WhatsApp session — mostly one-time setup + linking, then a
`lib/imessage.py`-shaped reader. Disk headroom needed (see the near-full-disk note from
2026-07-23) before standing up another datastore.
