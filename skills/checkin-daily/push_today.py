#!/usr/bin/env python3
"""push_today — render a passive daily glance into the synced "PA Today" Apple Note.

A cross-device convenience: because Apple Notes syncs over iCloud, writing today's picture
into a note puts it on Adam's phone with zero taps and no Signal round-trip. Read-only
sources (calendar, tasks, inbox counts) via the shared libs; the only write is replacing the
one PA-owned "PA Today" note.

Deliberately a *glance*: calendar + due tasks + inbox counts. It does NOT include mail
subjects — that keeps sensitive (e.g. legal) subject lines out of a passively-synced note,
honouring the PA/legal separation.

Usage: python3 skills/checkin-daily/push_today.py [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import html
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lib.applenotes import set_note  # noqa: E402
from lib.comms import ACCOUNTS, calendar_events, fetch_inbox, partition_inbox  # noqa: E402
from lib.taskstore import load_tasks  # noqa: E402

NOTE_TITLE = "PA Today"


def _due(day: date) -> list[dict]:
    """Open tasks due on/before `day`, soonest first."""
    tasks = [t for t in load_tasks() if not t.get("completed") and t.get("due_date")]
    return sorted((t for t in tasks if t["due_date"] <= day.isoformat()),
                  key=lambda t: t["due_date"])


def build_html(day: date) -> str:
    """Build the note body (HTML — Notes takes the first bold line as the title)."""
    esc = html.escape
    # First line must be exactly NOTE_TITLE — Apple Notes derives the note's *name* from it,
    # so a stable first line means set_note() updates one note instead of creating a new one
    # each refresh (the date goes on the second line).
    parts = [f"<div><b>{esc(NOTE_TITLE)}</b></div>",
             f"<div>{esc(day.strftime('%A %-d %B %Y'))}</div>", "<div><br></div>"]

    # Calendar, per account, kept separate.
    parts.append("<div><b>Today</b></div>")
    any_ev = False
    for acct in ACCOUNTS:
        evs = calendar_events(acct["cal"], day, day)
        if not evs:
            continue
        any_ev = True
        parts.append(f"<div>{esc(acct['id'])}:</div>")
        for ev in evs:
            loc = f" · {esc(ev['location'][:40])}" if ev["location"] else ""
            parts.append(f"<div>&nbsp;&nbsp;{esc(ev['when'])} — {esc(ev['title'])}{loc}</div>")
    if not any_ev:
        parts.append("<div>&nbsp;&nbsp;Nothing scheduled — the day is yours.</div>")

    # Due tasks.
    parts.append("<div><br></div><div><b>Due</b></div>")
    due = _due(day)
    if not due:
        parts.append("<div>&nbsp;&nbsp;Nothing due — no pressure.</div>")
    else:
        for t in due:
            overdue = " (overdue)" if t["due_date"] < day.isoformat() else ""
            parts.append(f"<div>&nbsp;&nbsp;☐ {esc(t['title'])} [{esc(t['category'])}]{overdue}</div>")

    # Inbox counts only (no subjects — keeps sensitive lines off a passively-synced note).
    parts.append("<div><br></div><div><b>Inbox</b></div>")
    for acct in ACCOUNTS:
        worth, noise = partition_inbox(fetch_inbox(acct["mail"]))
        parts.append(f"<div>&nbsp;&nbsp;{esc(acct['id'])}: {len(worth)} worth a look "
                     f"({noise} quiet)</div>")

    parts.append("<div><br></div><div>— your PA · auto-updated</div>")
    return "".join(parts)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Push today's glance into the PA Today note.")
    p.add_argument("--date", default=None, help="ISO date (default today)")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    day = date.fromisoformat(args.date) if args.date else date.today()
    ok = set_note(NOTE_TITLE, build_html(day))
    print(f"PA Today note updated: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
