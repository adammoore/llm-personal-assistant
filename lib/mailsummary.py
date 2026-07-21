#!/usr/bin/env python3
"""mailsummary — an on-demand ADHD-friendly summary of the inbox.

Like Magic ToDo but for mail: `claude -p` reads the (already noise-filtered) worth-a-look
list across both accounts and returns a short "who's waiting / what's time-sensitive" digest.
Cached to data/mail_summary.json so the dashboard can show it (with a timestamp) until the
next re-summarise. Read-only; no bodies are fetched, only the sender+subject shortlist.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.comms import ACCOUNTS, fetch_inbox, partition_inbox  # noqa: E402
from lib.taskstore import repo_root  # noqa: E402


def _cache() -> Path:
    return repo_root() / "data" / "mail_summary.json"


def load_summary() -> dict | None:
    """Return the cached {summary, at} or None."""
    p = _cache()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def summarize(*, now: datetime | None = None, timeout: int = 90) -> dict | None:
    """Summarise the inbox via claude, cache it, and return {summary, at}."""
    lines = []
    for acct in ACCOUNTS:
        worth, _ = partition_inbox(fetch_inbox(acct["mail"], limit=30))
        for m in worth[:12]:
            lines.append(f"[{acct['id']}] {m['from']}: {m['subject']}")
    if not lines:
        return None
    prompt = (
        "Summarise this inbox for an ADHD reader. Group into 'needs a reply' vs 'FYI', name "
        "who is waiting, flag anything time-sensitive, and keep the two accounts (personal / "
        "fairres) distinct. Be brief — at most 8 short lines, no preamble.\n\n" + "\n".join(lines)
    )
    try:
        out = subprocess.run(["claude", "-p", prompt],
                             capture_output=True, text=True, timeout=timeout)
    except (subprocess.SubprocessError, OSError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    stamp = (now or datetime.now()).isoformat(timespec="minutes")
    data = {"summary": out.stdout.strip(), "at": stamp}
    p = _cache()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def main() -> int:
    d = summarize()
    print(d["summary"] if d else "(no summary)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
