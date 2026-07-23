#!/usr/bin/env python3
"""imessage — read the local Messages database (chat.db), read-only.

Two jobs: (1) feed the unified comms inbox with recent iMessages, and (2) enable *phone
capture* — you text a designated prefix ("todo …", "pa …", "capture …") from your phone and
the monitor turns it into a task. No sends; opened read-only/immutable so it never locks
Messages. Requires Full Disk Access for whatever runs it (already granted).

Message text lives in `text`, or (newer macOS) only in the `attributedBody` typedstream blob,
which we decode best-effort.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB = Path.home() / "Library" / "Messages" / "chat.db"
_APPLE_EPOCH = 978307200  # 2001-01-01 in unix seconds
CAPTURE_PREFIXES = ("todo", "pa", "capture", "task")


def available() -> bool:
    """True if chat.db exists and is readable (Full Disk Access granted)."""
    if not DB.exists():
        return False
    try:
        _connect().execute("SELECT 1 FROM message LIMIT 1").fetchone()
        return True
    except sqlite3.Error:
        return False


def _connect() -> sqlite3.Connection:
    # immutable=1 avoids taking a lock on the live Messages DB.
    return sqlite3.connect(f"file:{DB}?mode=ro&immutable=1", uri=True, timeout=5)


def _apple_to_iso(raw: int) -> str:
    return (datetime(2001, 1, 1, tzinfo=timezone.utc)
            + timedelta(seconds=(raw or 0) / 1_000_000_000)).isoformat(timespec="minutes")


def _decode_attributed(blob: bytes | None) -> str | None:
    """Best-effort extraction of message text from an attributedBody typedstream blob."""
    if not blob:
        return None
    try:
        i = blob.index(b"NSString")
        i = blob.index(b"+", i) + 1
        n = blob[i]
        if n == 0x81:
            n = int.from_bytes(blob[i + 1:i + 3], "little")
            i += 2
        elif n == 0x82:
            n = int.from_bytes(blob[i + 1:i + 5], "little")
            i += 4
        return blob[i + 1:i + 1 + n].decode("utf-8", "replace").strip() or None
    except (ValueError, IndexError):
        return None


def _text(row_text: str | None, blob: bytes | None) -> str:
    return (row_text or _decode_attributed(blob) or "").strip()


def recent(days: int = 7, limit: int = 40) -> list[dict]:
    """Recent messages for the unified inbox: [{date, who, text, from_me}], newest first."""
    if not DB.exists():
        return []
    cutoff = int((datetime.now(timezone.utc).timestamp() - _APPLE_EPOCH - days * 86400)
                 * 1_000_000_000)
    q = ("SELECT m.date, m.is_from_me, h.id, m.text, m.attributedBody "
         "FROM message m LEFT JOIN handle h ON m.handle_id=h.ROWID "
         "WHERE m.date > ? AND (m.text IS NOT NULL OR m.attributedBody IS NOT NULL) "
         "ORDER BY m.date DESC LIMIT ?")
    out = []
    try:
        for date_raw, from_me, hid, txt, blob in _connect().execute(q, (cutoff, limit)):
            body = _text(txt, blob)
            if not body:
                continue
            out.append({"date": _apple_to_iso(date_raw), "who": "me" if from_me else (hid or "?"),
                        "text": body[:120], "from_me": bool(from_me)})
    except sqlite3.Error:
        return []
    return out


def captures(since_rowid: int = 0) -> tuple[list[dict], int]:
    """Self-sent messages that start with a capture prefix, newer than since_rowid.

    Returns ([{rowid, text}], max_rowid). The prefix keeps it deliberate — normal messages
    are never captured. Strips the prefix from the returned text.
    """
    if not DB.exists():
        return [], since_rowid
    q = ("SELECT m.ROWID, m.text, m.attributedBody FROM message m "
         "WHERE m.is_from_me=1 AND m.ROWID > ? ORDER BY m.ROWID ASC")
    caps, top = [], since_rowid
    try:
        for rowid, txt, blob in _connect().execute(q, (since_rowid,)):
            top = max(top, rowid)
            body = _text(txt, blob)
            low = body.lower()
            for pre in CAPTURE_PREFIXES:
                if low.startswith(pre + " ") or low.startswith(pre + ":"):
                    caps.append({"rowid": rowid, "text": body[len(pre):].lstrip(": ").strip()})
                    break
    except sqlite3.Error:
        return [], since_rowid
    return caps, top


def main() -> int:
    if not available():
        print("chat.db not readable — grant Full Disk Access.")
        return 0
    for m in recent(days=3, limit=8):
        print(f"{m['date']}  {'me→' if m['from_me'] else ''}{m['who']}: {m['text'][:50]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
