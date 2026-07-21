# ADR-003 — The Intertwingled, Faceted View (ZigZag / ZFR)

- **Status:** Proposed (awaiting GATE sign-off)
- **Date:** 2026-07-21
- **Owner:** Adam Vials Moore
- **Extends:** ADR-001, ADR-002; realises the ZigZag/ZFR vision (`data/reference/zephyrweb-zigzag-federated-metadata.md`)

## Context

The dashboard today is a fixed set of cards (Today / Tasks / Messages / Activity). Adam's
actual mental model — and his research life's work — is **ZigZag / ZFR**: everything
*intertwingled* (Nelson), no single hierarchy, and the ability to **follow a dimension /
thread** or **split into facets / contexts**. Two gaps make this concrete: Westminster work
comms aren't in the unified view at all, and there's no way to slice "everything" by a
dimension.

## Decision

Make the dashboard a **faceted view over one unified pool**. Every item — task, mail, event,
file, work comm, note — is one normalised node (extend `lib/activity.Activity`) carrying
**dimensions**, and the UI lets Adam pivot the same pool along any of them.

### Dimensions on every node
- **source** — task / mail / event / file / teams / slack
- **context** — personal / work / case  (derived; see rules)
- **theme** — free tag (Enact, ZigZag, House, …)
- **people** — sender / attendees where known
- **time** — timestamp (due / start / received)
- **status** — open / done / overdue / unread

### Context derivation (a rule table, not a hierarchy)
- **work** — Westminster/Enact sources (Outlook, Teams, Slack, OneDrive) or work themes.
- **case** — fairres legal mail, court dates, case themes. *Surfaced for visibility*
  (central-overview reframe) but never turned into legal work-product; case actions stay in
  the case tracks.
- **personal** — everything else (personal Gmail/Calendar, personal tasks).

### Westminster into the pool (answers "where's Westminster?")
`work-pull --cache` writes `data/work_cache.json` (per-source glance + timestamp). The
activity builder reads the cache, so work appears in the unified view **as of the last pull**
(with the timestamp shown). Refresh happens on demand, or via a light periodic pull while the
Enact Chrome is up. No live CDP on every dashboard render.

### The UI — follow threads, or split into facets
- A **facet bar**: chips for context (All · Personal · Work · Case), source, and active
  themes. Click a value to **follow that thread** — the whole view filters to it. Combine
  chips = intersection. Click again / "All" = clear.
- A **"split by" toggle**: group the pool into columns by a chosen dimension (e.g. by context
  → Personal | Work | Case; or by theme). This is the "split into facets/contexts" move.
- The current cards (Today / Tasks / Messages) become **saved facets** — pre-set lenses on
  the same pool, still interactive (capture / ✓ complete / ✨ breakdown intact).
- ZigZag principle: any dimension can be the axis; nothing is privileged; threads cross
  contexts (e.g. follow "Jenny Evans" across mail + meetings + tasks).

## Architecture

- `lib/activity.py` — add `context`, `people` to `Activity`; add a `from_work_cache()` source
  and context-derivation rules. `unified()` returns the full pool with dimensions.
- `skills/work-pull/pull.py` — add `--cache` to persist a compact `data/work_cache.json`.
- `build_pa_dashboard.py` — render the facet bar + "split by" + the faceted stream; keep the
  saved-facet cards. Facet state in the URL/localStorage so it survives refresh.
- Read-only + the existing interactive writes; no new outbound surface.

## Consequences

- **Positive:** the PA finally matches Adam's model — one pool, many lenses; Westminster is
  in the view; follow any thread or split by any facet. A small, real instance of ZFR.
- **Costs/risks:** more UI complexity (keep the facet bar quiet, default to the familiar
  cards); the unified pool can be large — cap/paginate per facet; work data is only as fresh
  as the last pull (show the timestamp). Case items surface across contexts — intended, his
  private device, but the case-work-product boundary still holds.

## Build order (after GATE)
1. `work-pull --cache` + `lib/activity` gains work source + context/people dimensions.
2. Facet bar (context/source/theme chips) filtering the existing cards + a unified stream.
3. "Split by" grouping (by context / theme).
4. Follow-a-thread on any facet value (incl. people). Polish + persistence.
