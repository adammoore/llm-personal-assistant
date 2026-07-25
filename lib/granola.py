#!/usr/bin/env python3
"""granola — themed meeting cache for the PA (write side).

Granola holds Adam's meeting notes across ALL themes — work (Enact/repository/metadata), case
(family court / legal / police), medical/CP (CAMHS, core group). The claude.ai Granola connector
is **agent-only** (a launchd builder can't reach it), so the flow is: an agent pulls meetings via
the connector and calls `write_cache()` here; `lib.activity.from_granola()` reads the result like
work_cache. This module owns the classification + cache shape so a refresh is one call.

Refresh (agent): list meetings via mcp__claude_ai_Granola__list_meetings, pass
[{"id","title","date"(ISO)}] to write_cache(). Kept dependency-free and deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path

CACHE = Path(__file__).resolve().parents[1] / "data" / "granola_cache.json"

# Context routing from the meeting title. Case first (the wall-relevant tag), then medical, else
# work — Adam's consultancy calls dominate, so work is the sensible default for the remainder.
_CASE = ("family court", "legal strateg", "legal service", "police", "divorce", "section 37",
         "non-molestation", "molestation", "isabella", " izzy", "danny", "bail", "allegation",
         "misrepresentation", "statement review", "core group", "vials moore")
_MEDICAL = ("camhs", "cahms", "alder hey", "cookson")


def classify(title: str) -> str:
    t = (title or "").lower()
    if any(k in t for k in _CASE):
        return "case"
    if any(k in t for k in _MEDICAL):
        return "medical"
    return "work"


def theme_of(title: str, ctx: str) -> str:
    """A short theme tag for the Nest sub-container / connection wiring."""
    t = (title or "").lower()
    if ctx == "case":
        return "family-court"
    if ctx == "medical":
        return "camhs" if "camhs" in t else "health"
    if "enact" in t:
        return "enact"
    if any(k in t for k in ("repositor", "metadata", "haiku", "licensing", "deposit", "sso",
                            "fair")):
        return "repository"
    if "pathfinder" in t:
        return "pathfinders"
    return "work"


def build_items(meetings: list[dict]) -> list[dict]:
    """Map raw connector meetings ({id,title,date}) to Activity-shaped, context-tagged items."""
    items = []
    for m in meetings:
        title = (m.get("title") or "").strip()
        if not title:
            continue
        ctx = classify(title)
        items.append({
            "source": "meeting", "type": "granola",
            "timestamp": (m.get("date") or "")[:10] or None, "title": title,
            "theme": theme_of(title, ctx), "priority": None, "url": None,
            "meta": {"id": m.get("id"), "context": ctx},
        })
    return items


def write_cache(meetings: list[dict], generated: str, path: Path | None = None) -> int:
    """Classify + persist meetings to the cache. `generated` is an ISO date (agent supplies it)."""
    path = path or CACHE
    items = build_items(meetings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated": generated, "source": "claude.ai Granola connector",
               "count": len(items), "items": items}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(items)
