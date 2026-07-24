#!/usr/bin/env python3
"""glance — pre-computed mail + calendar snapshot so dashboard *renders* without network.

The dashboard used to fetch mail (himalaya ×2) and calendar (gog ×2) live inside every render.
But render runs on every mutation — ticking a task done, pinning, editing — so a one-click action
waited ~7s for data it never touched. This splits the two concerns:

  refresh() — slow, network: fetch mail worth/noise + calendar (today..+2) → data/glance_cache.json
  load()    — fast, local:   read that cache; render reads this, never the network

refresh() runs on the monitor tick and on the explicit /refresh button; mutations only re-render,
which is now pure-local and instant. Read-only w.r.t. the mail/calendar sources.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.comms import ACCOUNTS, calendar_events, fetch_inbox, partition_inbox  # noqa: E402

GLANCE_CACHE = Path(__file__).resolve().parents[1] / "data" / "glance_cache.json"


# Horizon cached for calendar events — wide enough to feed the 14-day activity timeline; the
# today card filters to today and next-meeting to the soonest, both from this one cache.
EVENT_HORIZON_DAYS = 14


def refresh(path: Path = GLANCE_CACHE, today: date | None = None) -> dict:
    """Fetch mail (worth/noise per account) + calendar (today..+14 per account); write the cache."""
    today = today or date.today()
    data: dict = {"at": datetime.now().isoformat(timespec="seconds"), "mail": {}, "events": {}}
    for a in ACCOUNTS:
        worth, noise = partition_inbox(fetch_inbox(a["mail"]))
        # Slim to what the messages card renders (drop the bulky raw envelope).
        data["mail"][a["id"]] = {
            "worth": [{"from": w["from"], "subject": w["subject"],
                       "date": w["date"], "unread": w["unread"]} for w in worth],
            "noise": noise,
        }
        data["events"][a["id"]] = calendar_events(
            a["cal"], today, today + timedelta(days=EVENT_HORIZON_DAYS))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def load(path: Path = GLANCE_CACHE) -> dict:
    """Read the cache (or empty-but-valid defaults if it doesn't exist yet)."""
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"at": None, "mail": {}, "events": {}}
    d.setdefault("mail", {})
    d.setdefault("events", {})
    return d


def main() -> int:
    d = refresh()
    mail = sum(len(v.get("worth", [])) for v in d["mail"].values())
    evs = sum(len(v) for v in d["events"].values())
    print(f"glance refreshed: {mail} mail worth-a-look, {evs} events (today..+2)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
