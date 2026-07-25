#!/usr/bin/env python3
"""cider — read-only visitation into the sibling cider-store knowledge graph.

cider-store owns the legal case knowledge/document/graph (cross-project alignment; the PA builds
no doc store). This module is the PA's *read-only* window onto its provenance graph
(`~/cider-outputs/.store/knowledge.sqlite`), so the Nest can render the case principals' claim
connections at build time — "visitation, not copying": we reference in place, never mutate.

Wall discipline: everything here is case/legal content. It feeds ONLY the gated, off-by-default
case layer of Adam's private dashboard — never any outward-facing output. The live/agent path for
richer queries is the adam-mcp MCP tools (store_search / graph_neighbours / graph_path).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

_DB = Path.home() / "cider-outputs" / ".store" / "knowledge.sqlite"


def available() -> bool:
    return _DB.exists()


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{_DB}?mode=ro", uri=True, timeout=5)


def person_claims(slug: str, limit: int = 24) -> list[dict]:
    """Claims linked to person:<slug> in the graph — {id, label, status, edge, note}.

    Read-only and defensive: any error (missing DB, schema drift) yields an empty list so a
    build never fails on cider being absent or mid-migration.
    """
    if not slug or not available():
        return []
    node = f"person:{slug}"
    try:
        con = _connect()
        rows = con.execute(
            """
            SELECT n.id, n.label, n.attrs, e.type, e.note
            FROM edges e
            JOIN nodes n
              ON n.id = CASE WHEN e.src = ? THEN e.dst ELSE e.src END
            WHERE (e.src = ? OR e.dst = ?) AND n.type = 'claim'
            ORDER BY n.id
            LIMIT ?
            """,
            (node, node, node, limit),
        ).fetchall()
        con.close()
    except sqlite3.Error:
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for nid, label, attrs, etype, note in rows:
        if nid in seen:
            continue
        seen.add(nid)
        status = ""
        try:
            status = (json.loads(attrs or "{}") or {}).get("factual_status", "")
        except (ValueError, TypeError):
            pass
        out.append({"id": nid, "label": label or nid, "status": status,
                    "edge": etype or "", "note": note or ""})
    return out


def stats() -> dict:
    """Small health snapshot (node/edge counts) — defensive."""
    if not available():
        return {}
    try:
        con = _connect()
        n = con.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        e = con.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        con.close()
        return {"nodes": n, "edges": e}
    except sqlite3.Error:
        return {}


def main() -> int:
    print("cider-store:", "available" if available() else "absent", stats())
    for slug in ("cora", "isaac", "gwen"):
        cs = person_claims(slug)
        print(f"\nperson:{slug} — {len(cs)} claims")
        for c in cs[:6]:
            print(f"  [{c['status'] or '—':16}] {c['label'][:76]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
