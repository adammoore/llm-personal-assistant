# PA → cider-store hand-off

From the **llm-personal-assistant (PA)** Claude Code session to the **cider-store** development
session. Written 2026-07-25. Companion to `~/adam-mcp/cider-store/docs/07_CROSS_PROJECT_ALIGNMENT.md`.

The PA↔cider identity + interop alignment is **live on the PA side**. This is cider-store's half.

---

## Status (what's already true)

- ✅ **PA carries the shared `person:<slug>` key.** `lib/people.person_slug()` + a `slug` field
  backfilled onto all people. Verified against your graph: `Cora Vials Moore` **and** `Cora Vials`
  → `person:cora`; `Isaac James Vials Moore` → `person:isaac`; `Isabella Martin` →
  `person:isabella-martin`.
- ✅ **PA reads your activity cache.** `lib/activity.from_cider()` already reads
  `~/cider-outputs/.store/activity_cache.json` defensively (like `work_cache.json`).
- ✅ **Shared ZigZag dimensions** (`source · context · theme · people · time · status`) are what the
  PA's Nest view groups and wires by.
- ✅ **Your MCP tools are registered in the server** (`store_search`, `store_get_document`,
  `graph_neighbours`, `graph_path`, `store_stats`, `store_add_node`, `store_add_edge`,
  `store_ingest_path` — confirmed in `server.py` + `cider-store/src/…/mcp_tools.py`).

The **one blocker**: the adam-mcp server isn't in Claude Code's MCP config, so no session can call
those tools. Fixing that (#1) unblocks the real payoff — the Nest's connection lines driven by
`graph_neighbours` instead of keyword matching.

---

## Asks

### 1. Register adam-mcp with Claude Code (the blocker)

Your server (`~/adam-mcp/server.py`, **stdio**, `FastMCP name="adam-legal-case-tools"`) has the
tools, but `mcpServers` is empty in Claude Code's config — nothing can ToolSearch it. Neither
system `python3` has the deps (`fastmcp`, `sqlite-vec`, `model2vec`) and `mcp_tools` lives in
`cider-store/src` — so it must run from **your venv** with that on `PYTHONPATH`.

Add it at **user scope** (so both PA and cider sessions see it):

```bash
claude mcp add adam-mcp -s user -- <venv-python> /Users/adamvialsmoore/adam-mcp/server.py
# or, if it needs cwd/PYTHONPATH for the mcp_tools import:
claude mcp add adam-mcp -s user -- bash -c \
  'cd /Users/adamvialsmoore/adam-mcp && exec <venv-python> server.py'
claude mcp list          # adam-mcp should appear
```

Then restart the PA session — it will ToolSearch `store_search` / `graph_neighbours` / etc.

### 2. Add the reverse person cross-ref

The PA emits the shared `person:<slug>` + its `people.json` int id. On your person nodes, set
`attrs.pa_people_id`:

| cider node | pa_people_id |
|------------|--------------|
| `person:cora` | **14** (primary; PA also has a duplicate entry #35 → same `person:cora`) |
| `person:isaac` | **21** |
| `person:gwen` | — (not a PA correspondent) |
| `person:adam` | — (self; excluded from `people.json`) |

### 3. Slug convention (locked — follow for new person nodes)

`person:<slug>` where the **four principals use short first-name slugs** (`adam` / `cora` / `gwen`
/ `isaac`) and **everyone else is `person:firstname-lastname`** (`person:isabella-martin`,
`person:henry-williams`, …). Same real person → same slug (the multi-contextual identifier).

### 4. (High value) Emit `activity_cache.json`

Write `~/cider-outputs/.store/activity_cache.json` in the PA's `Activity` shape:

```json
{ "items": [
  { "source": "document|chunk|claim|evidence", "type": "…", "timestamp": "ISO|null",
    "title": "…", "theme": "…|null", "priority": "…|null", "url": "…|null",
    "meta": { "context": "personal|work|case", "people": ["person:cora"], "status": "…" } }
]}
```

The PA **already reads it** — no PA change needed. Recent/pinned knowledge atoms will appear in the
PA timeline and the Nest automatically. Tag `context` (from `track`) and `people` (slugs) at
minimum.

### 5. The wall (unchanged)

Tag atoms with `context`/`track`; `store_search` defaults to `context=personal|work`, gating
`case/legal` unless explicitly requested. The PA honours this for its outputs. Doctrine both
projects share: **visitation not copying** — reference in place, preserve provenance.

---

## What the PA provides you

- The **canonical people list** (`data/people.json`): name, `slug`, `kind` (person|org), `circle`
  (inner|close|wider|peripheral), `priority`, attention signals, `interactions`.
- The **`Activity` node schema** (`lib/activity.py`) — the shared unified-node shape.
- A **Nest UI** ready to render your `graph_neighbours` edges as traced connections across
  bounded, nested containers (Nelson / Tinderbox style).
