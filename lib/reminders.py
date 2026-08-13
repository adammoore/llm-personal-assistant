#!/usr/bin/env python3
"""reminders — read Apple Reminders (incomplete items) directly from its Core Data store.

Apple Reminders is Adam's always-with-him capture surface: Siri ("remind me to…"), the
Reminders app, and the OpenClaw WhatsApp agent all file here. The PA surfaces the *open*
items alongside its own tasks for one coordinated view. Read-only — never writes.

Why not AppleScript? The Reminders scripting bridge (EventKit/iCloud) is pathologically slow
here — a bare `name of reminders` times out past 60s. Instead we read the Core Data SQLite
store the way lib.imessage reads chat.db. Freshly-added reminders live in the `-wal` sidecar,
so we copy each store + its `-wal`/`-shm` to a temp dir and read the copy (immutable reads of
the live file skip the WAL and miss anything added in the last few minutes — exactly the
WhatsApp-capture case). Dates are Core Data epoch (2001-01-01), like Apple's other stores.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))   # so `python3 lib/reminders.py` can import lib.* (the task filter)
CACHE_PATH = REPO / "data" / "reminders_cache.json"
STORE_DIR = (Path.home() / "Library" / "Group Containers"
             / "group.com.apple.reminders" / "Container_v1" / "Stores")
_CORE_DATA_EPOCH = 978307200  # 2001-01-01 in unix seconds

# Incomplete reminders + best-effort list name (the ZLIST join often yields null names across
# Core Data's single-table inheritance, so we coalesce a few candidates and tolerate blanks).
_QUERY = """
SELECT r.ZTITLE,
       CASE WHEN r.ZDUEDATE IS NULL THEN NULL ELSE r.ZDUEDATE END,
       COALESCE(l.ZNAME1, l.ZNAME, l.ZTITLE, '')
FROM ZREMCDREMINDER r
LEFT JOIN ZREMCDOBJECT l ON r.ZLIST = l.Z_PK
WHERE r.ZCOMPLETED = 0 AND r.ZTITLE IS NOT NULL AND TRIM(r.ZTITLE) <> ''
  -- Exclude the PA's OWN pushed tasks (lib.remindpush) so reading Reminders doesn't re-ingest
  -- them as duplicate tasks — the read/write loop cider's handover §4.1 warns about.
  AND COALESCE(l.ZNAME1, l.ZNAME, l.ZTITLE, '') <> 'PA Tasks'
"""


def _stores() -> list[Path]:
    return sorted(STORE_DIR.glob("Data-*.sqlite")) if STORE_DIR.exists() else []


def available() -> bool:
    """True if the Reminders Core Data store exists (needs Full Disk Access to read)."""
    return bool(_stores())


def _iso(cd_ts: float | None) -> str | None:
    if cd_ts is None:
        return None
    return (datetime(2001, 1, 1, tzinfo=timezone.utc)
            + timedelta(seconds=cd_ts)).astimezone().isoformat(timespec="minutes")


def open_reminders() -> list[dict]:
    """All incomplete reminders across every store: [{title, due, list}], soonest-due first.

    Copies each store + its WAL sidecar to a temp dir so recently-added items are visible.
    """
    out: list[dict] = []
    stores = _stores()
    if not stores:
        return out
    with tempfile.TemporaryDirectory(prefix="pa_rem_") as td:
        tmp = Path(td)
        for i, store in enumerate(stores):
            dst = tmp / f"s{i}.sqlite"
            try:
                shutil.copy2(store, dst)
                for ext in ("-wal", "-shm"):      # copy sidecars if present (WAL = fresh data)
                    side = store.with_name(store.name + ext)
                    if side.exists():
                        shutil.copy2(side, dst.with_name(dst.name + ext))
                con = sqlite3.connect(f"file:{dst}?mode=ro", uri=True, timeout=5)
                for title, due, lname in con.execute(_QUERY):
                    out.append({"title": (title or "").strip(),
                                "due": _iso(due), "list": (lname or "").strip()})
                con.close()
            except (OSError, sqlite3.Error):
                continue
    # Dedup (a reminder can appear in mirrored stores), then soonest-due first, undated last.
    seen, uniq = set(), []
    for r in out:
        key = (r["title"], r["due"])
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    uniq.sort(key=lambda e: (e["due"] is None, e["due"] or "", e["title"].lower()))
    return uniq


def write_cache(path: Path = CACHE_PATH) -> dict:
    """Snapshot open reminders for the dashboard. Shape: {at, ok, items:[...]}."""
    now = datetime.now().isoformat(timespec="seconds")
    if not available():
        data = {"at": now, "ok": False,
                "note": "Reminders store not found / unreadable (needs Full Disk Access).",
                "items": []}
    else:
        items = open_reminders()
        # Drop reminders that duplicate an open PA task — including lib.remindpush's own 'PA Tasks'
        # pushes (the Core Data list-name join is unreliable, so match on title). Without this,
        # reading Reminders re-ingests the tasks the PA just wrote there (cider handover §4.1 loop).
        try:
            from lib.taskstore import load_tasks
            task_titles = {(t.get("title") or "").strip().lower()
                           for t in load_tasks() if not t.get("completed")}
            items = [r for r in items if (r.get("title") or "").strip().lower() not in task_titles]
        except (ImportError, OSError, ValueError):
            pass
        data = {"at": now, "ok": True, "items": items}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def main() -> int:
    data = write_cache()
    if not data["ok"]:
        print(data.get("note", "unavailable"))
        return 0
    print(f"{len(data['items'])} open reminders:")
    for it in data["items"]:
        due = f"  (due {it['due']})" if it["due"] else ""
        lst = f"[{it['list']}] " if it["list"] else ""
        print(f"  • {lst}{it['title']}{due}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
