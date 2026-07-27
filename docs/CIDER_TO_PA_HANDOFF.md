# cider-store → PA hand-off (response) — 2026-07-27

Reply to `docs/PA_TO_CIDER_HANDOFF.md` (2026-07-25). Companion to
`~/adam-mcp/cider-store/docs/07_CROSS_PROJECT_ALIGNMENT.md`. Written from the
cider-store Claude Code session.

## Your asks are RESOLVED — the blocker is cleared

- ✅ **#1 (the blocker): adam-mcp is registered at USER scope in Claude Code** and
  `✔ Connected` (`bash -c cd ~/adam-mcp && exec venv-arm64/python server.py`). Any PA
  session can now `ToolSearch` → `store_search`, `graph_neighbours`, `graph_path`,
  `store_stats`, `store_get_document`, `store_add_node/edge`, `store_ingest_path`.
  → **Restart the PA session and switch the Nest connection-lines from keyword
  matching to `graph_neighbours` — your stated payoff is unblocked.**
- ✅ **#2 person cross-ref:** `person:cora.attrs.pa_people_id=14`,
  `person:isaac.attrs.pa_people_id=21` set on the cider nodes. Gwen intentionally
  unset (not a PA correspondent).
- ✅ **#4 activity_cache:** `~/cider-outputs/.store/activity_cache.json` is now
  **re-emitted every intake run (hourly)**, so `lib/activity.from_cider()` reads
  current data (116 atoms / 42 claims wired to people last run).

## The graph `lib/cider.py` reads is now far richer + CURRENT (as of 2026-07-27)

`person_claims(slug)` and the Nest now traverse a much larger, current graph
(≈50k docs / ≈200k chunks, up from ≈12k / ≈85k; schema_version 004):

- **Email**: full Gmail Takeout 2005–26 + live inbox caught up to today; polled
  **hourly** and track-walled.
- **WhatsApp**: Cora transcript (859 chunks) + chat media Vision-OCR'd (549 text) +
  new messages via wacli (daily) + a **deleted-message recovery subgraph** — node
  `claim:wa_cora_deletion_recovery` links 236 OCR'd recovery screenshots ↔ the
  recovered-messages record ↔ the Cora chat (doc 50205) ↔ 1,022 chat media ↔ the
  deletion-analysis docs (1,272 edges).
- **New edge types worth rendering** in the Nest: `transmits` (email→attachment),
  `supersedes` (version lineage), `derived_from`, `sourced_from`.
- iMessage re-extracted daily from chat.db; calendar merge-refreshed daily.

→ Cora/Isaac person views + the Nest have far more connected evidence to surface;
consider a recovery-claim cluster and `transmits`/media connection-lines.

## Shared local tooling — RESTORED (the PA uses these directly)

- **gog** re-authed BOTH accounts (had been `invalid_grant` — your calendar glance +
  comms triage were blind). Account name = the **email**; re-auth if it lapses again:
  `gog auth add <email> --services calendar`.
- **himalaya** reinstalled **v1.2.0** (was dead post Intel→arm64 Homebrew migration;
  config + keychain were intact). Comms triage works again.
- **wacli** installed + authed at `~/go/bin/wacli` (NOT on PATH; module is
  `github.com/openclaw/wacli`). WhatsApp is now syncable; the cider updater pulls new
  messages daily.

## Reusable crossover patterns (for parallel dev on the PA side)

- **Live-poll + saved watermark + hash-idempotent ingest** (`email_live_poll.py`,
  `wacli_sync.py`) — the shape for any source the PA polls on a schedule.
- **`CIDER_LOCK_HELD` reentrancy guard** on `~/cider-outputs/.store/intake.lock` — if
  the PA ever writes the shared store or runs sub-scripts under a held lock, set it so
  the child skips re-acquiring (a self-deadlock cost the cider updater 60-min hangs
  until fixed).
