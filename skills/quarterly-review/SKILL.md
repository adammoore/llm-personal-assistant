---
name: quarterly-review
description: Assemble a DRAFT quarterly review from real activity so Adam has usable material to shape. Use when Adam wants to look back over a quarter, prep a review, or "what did I actually do this quarter". Pulls daily/weekly/monthly notes, task activity, git history, Granola meetings, and the evidence store; synthesises a draft in Adam's voice for him to edit. Draft generator only — never sends or mutates anything.
---

# quarterly-review

Turn a quarter of scattered activity into a **draft review Adam can edit** — grounded in
what actually happened, not what he thinks he remembers. This is a **draft generator, not a
report card and not a sender**. Wins surface first; gaps are open threads, never debt.

## Autonomy (ADR-001 §7 / autonomy.yaml)

- Assembling + summarising notes/tasks/git/meetings/evidence (`assemble.py`, MCP reads) →
  **autonomous** (read-only `summarize`).
- Writing the raw-material digest and the DRAFT review to `data/reviews/<quarter>.md` →
  **autonomous-but-flagged** (surface it for review; never treated as final).
- **Nothing here sends, drafts mail, or modifies a calendar, task, or evidence record.**

## Flow

1. **Assemble the deterministic local material** (no MCP, no network):
   ```bash
   python3 skills/quarterly-review/assemble.py            # current calendar quarter
   python3 skills/quarterly-review/assemble.py --from 2026-07-01 --to 2026-09-30
   ```
   This reads `data/daily/`, `data/weekly/`, `data/monthly/` notes whose date falls in
   range (lifting intentions/reflections/"what changed"/wins), summarises task activity
   from the local store (created-in-range by category; completed items as wins), and
   summarises git history via a read-only `git log`. It prints a markdown digest and writes
   it to `data/reviews/<quarter>.md` (e.g. `2026-Q3.md`). Note the quarter label it reports.

2. **Enrich with Granola meetings** (needs MCP at runtime). Discover the tools first:
   ```
   ToolSearch: "select:mcp__claude_ai_Granola__list_meetings,mcp__claude_ai_Granola__query_granola_meetings,mcp__claude_ai_Granola__get_meetings"
   ```
   Use `list_meetings` with `time_range: "custom"` and the quarter's `custom_start` /
   `custom_end` to enumerate meetings in range, then `query_granola_meetings` for themes,
   decisions and action items across them (preserve its inline citation links), and
   `get_meetings` to pull detail on the handful that matter. Summarise meetings — do not
   dump transcripts.

3. **Enrich with the adam-local evidence store / daily-notes tools** (also runtime MCP).
   These aren't loaded by default; discover them by capability:
   ```
   ToolSearch: "evidence store search in range"
   ToolSearch: "daily notes list read"
   ```
   Summarise evidence items and any longer-form notes that fall in the quarter. **Keep the
   PA / case boundary:** surface case-track evidence at the level of "what happened this
   quarter" for the review, but do not pull substantive legal content, allegations, or
   diagnostic framings into the PA review — that lives in the case tracks, not here.

4. **Synthesise the DRAFT review** in Adam's voice, appending to (or rewriting) the same
   `data/reviews/<quarter>.md`. Structure it as:
   - **Accomplishments** — concrete things shipped/done/moved (from wins, tasks, git, meetings).
   - **Themes** — the 3-5 threads the quarter actually clustered around.
   - **Meetings** — a short digest of what the Granola meetings advanced (with citations).
   - **What changed** — deltas since the start of the quarter (from monthly "what changed" notes).
   - **Open threads** — carried-forward items, framed as live and pick-up-able, **not** as failures.
   Write plainly and warmly, first person, brief. Mark it clearly as a **draft for Adam to edit**.

5. **Hand it back.** Show the draft (or its path) in chat and invite edits. Do not send it
   anywhere, post it, or turn it into tasks unless Adam explicitly asks — and even then,
   capture via `task-capture`, never silently.

## Guardrails

- **Draft only.** This skill never sends, publishes, or mutates mail/calendar/tasks/evidence.
- **Surface wins, don't itemise gaps as failures** — open threads are live work, not debt.
- **Read-only enrichment.** Granola and evidence tools are used to *read and summarise* only.
- **PA is not CIDER / the case.** Keep legal-track substance out of the PA review; reference
  activity at review altitude, don't reconstruct case content here.
- If a source is unavailable (Granola offline, no evidence tool, git absent), say so plainly
  and draft from what's there. A review should degrade gracefully, never hard-fail.
