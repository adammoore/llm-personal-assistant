#!/usr/bin/env python3
"""wall — the case/legal boundary as ONE policy, not a per-feature caveat.

Cross-project alignment (see the cider-store alignment): case/legal/medical content is walled off
from PA **outputs** and **default cross-store queries**. The PA's own private glance MAY surface
case for Adam's visibility (the central-overview reframing), but it must be a DELIBERATE, gated
reveal — never the default. Now that cider-store's whole corpus is one `store_search` away, the
wall has to hold everywhere (recall, focus, brief, Nest) from a single source of truth — this
module — rather than being re-remembered in each feature.

Two enforcement points:
  • `is_walled(context)`         — classify a context/track as behind-the-wall.
  • `filter_results(results)`    — drop walled chunks from a cider store_search result set unless
                                   case was explicitly requested (store_search gates INclusively
                                   by track, so keeping case OUT is done by filtering).
"""

from __future__ import annotations

# Contexts the PA operates in openly (the default surface).
OPEN = ("personal", "work")

# Contexts behind the wall — shown only on explicit request or a gated toggle. Includes the PA's
# own context tags and cider-store's track names (criminal|cp|family|financial), so one check
# spans both vocabularies.
WALLED = ("case", "legal", "medical", "local-authority", "cp", "criminal", "family", "financial",
          "safeguarding", "police")

# Path fragments that mark walled material in a store_search chunk's source_path. Fallback for
# when the store's per-hit track/context metadata isn't present (older server); the metadata check
# in _chunk_is_walled is authoritative once cider-store's track/context/doc_kind ride each hit.
_WALLED_PATH = ("criminal_track", "/case/", "_case_", "narrative_register", "familycourt",
                "legal_track", "/legal", "iuc_evidence", "iuc_rebuttal", "evidence_pack",
                "cv_register", "cv_contempt", "cora_analysis", "stark", "master_evidence",
                "corroboration_register", "rebuttal", "familycourt_read")

# One-line discipline to drop into an agent prompt that may call store_search.
GUIDANCE = ("Default cider queries to context=personal|work; never surface case/legal/medical "
            "content unless Adam explicitly asks for that theme. Use lib.wall.filter_results().")


def is_walled(context: str | None) -> bool:
    """True if a context/track tag names walled (case/legal/medical/...) material."""
    return (context or "").strip().lower() in WALLED


def _chunk_is_walled(r: dict) -> bool:
    ctx = r.get("track") or r.get("context") or (r.get("meta") or {}).get("context")
    if is_walled(ctx):
        return True
    path = (r.get("source_path") or "").lower()
    return any(frag in path for frag in _WALLED_PATH)


def filter_results(results: list[dict], *, allow_case: bool = False) -> list[dict]:
    """Return `results` with walled chunks removed, unless case was explicitly requested.

    `allow_case=True` is the deliberate, per-request opt-in (Adam focusing a case theme, or a
    gated reveal) — it returns everything. Otherwise every walled chunk is dropped.
    """
    if allow_case:
        return list(results)
    return [r for r in results if not _chunk_is_walled(r)]


def wants_case(theme_or_query: str | None) -> bool:
    """Heuristic: did the human deliberately point at a walled theme? (→ allow_case)."""
    return is_walled(theme_or_query) or any(
        w in (theme_or_query or "").lower()
        for w in ("case", "court", "legal", "police", "fdr", "family court", "cora", "medical"))
