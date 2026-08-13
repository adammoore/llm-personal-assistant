#!/usr/bin/env python3
"""whatsapp — recent RECEIVED WhatsApp messages via wacli, for event detection + the inbox.

Read-only and bounded: `wacli messages list --after <days> --from-them --json --read-only` — a
small window of incoming messages, `--read-only` so it never fights wacli's daily sync write-lock.
Field access is defensive (wacli's exact keys can shift); a bad shape yields [] rather than raising.
Returns the same `{text, date, sender, source}` shape the event detector and unified inbox consume.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import date, timedelta


def _wacli() -> str | None:
    for p in (shutil.which("wacli"), os.path.expanduser("~/go/bin/wacli")):
        if p and os.path.exists(p):
            return p
    return None


def available() -> bool:
    return _wacli() is not None


def recent(days: int = 2) -> list[dict]:
    """Received WhatsApp messages from the last `days` — [{text, date, sender, source}]."""
    exe = _wacli()
    if not exe:
        return []
    after = (date.today() - timedelta(days=days)).isoformat()
    try:
        r = subprocess.run(
            [exe, "messages", "list", "--after", after, "--from-them", "--json", "--read-only"],
            capture_output=True, text=True, timeout=25)
        data = json.loads(r.stdout or "[]")
    except (subprocess.SubprocessError, OSError, ValueError):
        return []
    items = data if isinstance(data, list) else data.get("messages", data.get("items", []))
    out = []
    for m in items:
        if not isinstance(m, dict):
            continue
        text = m.get("text") or m.get("body") or m.get("content") or ""
        if not text:
            continue
        ts = m.get("timestamp") or m.get("time") or m.get("date") or ""
        sender = (m.get("chatName") or m.get("pushName") or m.get("sender")
                  or m.get("chat") or m.get("name") or "whatsapp")
        out.append({"text": str(text)[:400], "date": str(ts)[:19],
                    "sender": str(sender)[:40], "source": "whatsapp"})
    return out


def main() -> int:
    ms = recent()
    print(f"whatsapp: {'available' if available() else 'wacli not found'} — "
          f"{len(ms)} received in last 2 days")
    for m in ms[:8]:
        print(f"  [{m['date'][:16]}] {m['sender']}: {m['text'][:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
