#!/usr/bin/env python3
"""work-pull — read Adam's already-open, logged-in Westminster/Enact work tabs (on-demand).

His `Start Enact Role Dashboard.command` launches a dedicated Chrome profile with remote
debugging on 127.0.0.1:9222, pre-opened to Outlook mail/calendar, Teams, and Slack. This reads
the *visible text* of those tabs over CDP (via lib.cdp) so the PA can summarise work comms
without any credentials, scraping of a login, or continuous session. Read-only: it never
clicks, sends, or navigates.

On-demand only (not part of the always-on monitor — a live browser session can't be a daemon).

Usage: python3 skills/work-pull/pull.py [--source mail|calendar|teams|slack]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lib.cdp import is_up, read_best  # noqa: E402

# Where the dashboard reads a compact snapshot of the work surfaces from (see --cache).
CACHE_PATH = REPO / "data" / "work_cache.json"

# Each work surface: a tab URL fragment + prioritised selectors (best-effort; DOM shifts).
SOURCES = [
    {"id": "mail", "label": "Outlook — mail", "url": "outlook.cloud.microsoft/mail",
     "selectors": ['div[aria-label="Message list"]', '[role=main]']},
    {"id": "calendar", "label": "Outlook — calendar", "url": "outlook.cloud.microsoft/calendar",
     "selectors": ['[role=main]', '[aria-label*="Calendar"]']},
    {"id": "teams", "label": "Teams", "url": "teams.microsoft.com",
     "selectors": ['[role=main]', '#app']},
    {"id": "slack", "label": "Slack (Notch8)", "url": "app.slack.com",
     "selectors": ['.p-workspace__primary_view', '[role=main]']},
]


def build(only: str | None) -> str:
    """Assemble a raw work glance from the open tabs (for a skill to summarise)."""
    if not is_up():
        return ("_Enact Chrome isn't running. Launch it with "
                "`~/Desktop/Start Enact Role Dashboard.command`, then try again._\n")
    lines = ["# Work glance (Westminster / Enact) — read-only from open tabs", ""]
    for src in SOURCES:
        if only and src["id"] != only:
            continue
        text = read_best(src["url"], src["selectors"])
        lines.append(f"## {src['label']}")
        if not text:
            lines.append(f"_Tab not open ({src['url']}). Open it in the Enact Chrome._\n")
        else:
            lines.append(text.strip() + "\n")
    return "\n".join(lines) + "\n"


def write_cache(path: Path = CACHE_PATH) -> dict:
    """Write a compact snapshot of the work surfaces for the dashboard to read.

    Shape: {"at": ISO-timestamp, "up": bool, "sources": [{id, label, text}]}. `text` is a
    trimmed (~1200 char) glance of each surface's visible tab text — no bodies fetched, just
    the same read_best the on-demand path uses. If the Enact Chrome isn't up we still write a
    marker (up=false, empty sources, plus a "launch" note) so the dashboard can show status.
    """
    now = datetime.now().isoformat(timespec="seconds")
    up = is_up()
    if not up:
        data = {
            "at": now,
            "up": False,
            "note": ("Enact Chrome not running — launch "
                     "`~/Desktop/Start Enact Role Dashboard.command`."),
            "sources": [],
        }
    else:
        sources = []
        for src in SOURCES:
            text = read_best(src["url"], src["selectors"])
            # Trim to a compact snippet; empty tab (not open) becomes an empty string.
            snippet = (text or "").strip()[:1200]
            sources.append({"id": src["id"], "label": src["label"], "text": snippet})
        data = {"at": now, "up": True, "sources": sources}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Read the open Westminster/Enact work tabs.")
    p.add_argument("--source", default=None, choices=[s["id"] for s in SOURCES],
                   help="restrict to one surface")
    p.add_argument("--cache", action="store_true",
                   help=f"write a compact snapshot to {CACHE_PATH.name} for the dashboard")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.cache:
        data = write_cache()
        print(f"wrote {CACHE_PATH} (up={data['up']}, {len(data['sources'])} sources)")
        return 0
    print(build(args.source))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
