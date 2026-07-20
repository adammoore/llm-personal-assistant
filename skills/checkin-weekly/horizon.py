#!/usr/bin/env python3
"""checkin-weekly horizon — gather a two-week deadline horizon and a loose-thread sweep.

The read-only data-gathering half of the `checkin-weekly` skill (ADR-001 §goals 5). Where
`checkin-daily` looks at *today*, this steps back to the week: the calendar out to a 14-day
horizon (across both accounts, kept separate — ADR-001 §4) and the open task store, so
threads that have quietly gone overdue get picked up rather than left to accrete.

Everything here is at the *autonomous* tier: it only reads and summarises (gog for calendar,
the local task store). No sends, no writes to Google. The one write is the durable weekly-note
stub under data/weekly/ (autonomous-but-flagged), mirroring glance.py's daily-note pattern.

Output: a calm markdown "weekly horizon" to stdout (the skill frames it as an invitation).

Usage: python3 skills/checkin-weekly/horizon.py [--date YYYY-MM-DD] [--days 14]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lib.comms import ACCOUNTS, calendar_events  # noqa: E402
from lib.taskstore import CATEGORIES, load_tasks, repo_root  # noqa: E402


def horizon_events(cal_account: str, start: date, end: date) -> list[dict]:
    """Events across the [start, end] horizon for one account (thin wrapper)."""
    return calendar_events(cal_account, start, end)


def open_tasks() -> list[dict]:
    """All open (not-completed) tasks from the local store."""
    return [t for t in load_tasks() if not t.get("completed")]


def loose_threads(day: date, week_end: date) -> dict[str, list[dict]]:
    """Open tasks grouped by category, keeping only overdue + due-this-week ones.

    A loose thread is anything already overdue or falling due on/before the end of this
    week — the things most likely to have slipped quietly. Undated tasks are left out here
    (they carry no deadline pressure); the skill can still surface them by judgement.
    """
    horizon = week_end.isoformat()
    grouped: dict[str, list[dict]] = {}
    for t in open_tasks():
        due = t.get("due_date")
        if not due or due > horizon:
            continue
        cat = t.get("category") if t.get("category") in CATEGORIES else "Other"
        grouped.setdefault(cat, []).append(t)
    # Soonest-due first within each category, so the most pressing thread reads at the top.
    for cat in grouped:
        grouped[cat].sort(key=lambda x: (x.get("due_date") or "9999", x["id"]))
    return grouped


def build_horizon(day: date, days: int) -> str:
    """Assemble the markdown weekly horizon."""
    end = day + timedelta(days=days)
    week_end = day + timedelta(days=(6 - day.weekday()))  # this Sunday (ISO week end)
    lines = [f"# Weekly horizon — week of {day.strftime('%A %-d %B %Y')}", ""]

    # Deadline horizon: the next `days` days, per account, kept separate.
    lines.append(f"## Deadline horizon — next {days} days")
    any_events = False
    for acct in ACCOUNTS:
        evs = horizon_events(acct["cal"], day, end)
        if not evs:
            continue
        any_events = True
        lines.append(f"\n**{acct['id']}** ({acct['cal']})")
        for ev in evs:
            loc = f" · {ev['location'][:40]}" if ev["location"] else ""
            lines.append(f"- {ev['date']} {ev['when']} — {ev['title']}{loc}")
    if not any_events:
        lines.append("\n_A clear horizon — nothing booked in the next fortnight._")

    # Loose-thread sweep: overdue + due-this-week open tasks, grouped by category.
    threads = loose_threads(day, week_end)
    lines.append("\n## Loose threads — overdue + due this week")
    if not threads:
        lines.append("\n_No threads hanging — nothing overdue or due this week._")
    else:
        today_iso = day.isoformat()
        # Follow the fixed category order so the sweep reads the same way every week.
        for cat in CATEGORIES:
            group = threads.get(cat)
            if not group:
                continue
            lines.append(f"\n**{cat}**")
            for t in group:
                overdue = f" (was due {t['due_date']})" if t["due_date"] < today_iso else \
                          f" (due {t['due_date']})"
                lines.append(f"- #{t['id']} {t['title']}{overdue}")

    return "\n".join(lines) + "\n"


def week_slug(day: date) -> str:
    """ISO week label (YYYY-Www) — a stable, sortable name for the weekly note."""
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def write_weekly_note(day: date, horizon: str) -> Path:
    """Write/refresh the weekly-note stub (durable trace); leaves the reflection for the skill."""
    note = repo_root() / "data" / "weekly" / f"{week_slug(day)}.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    if not note.exists():
        body = (horizon + "\n## Reflection\n_(one action-learning question — optional, skippable)_\n"
                "\n## Loose threads picked up\n_(added during check-in — only what Adam names)_\n")
        note.write_text(body, encoding="utf-8")
    return note


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gather the weekly check-in horizon.")
    p.add_argument("--date", default=None, help="ISO date (default: today)")
    p.add_argument("--days", type=int, default=14, help="deadline-horizon length in days")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    day = date.fromisoformat(args.date) if args.date else date.today()
    horizon = build_horizon(day, args.days)
    note = write_weekly_note(day, horizon)
    print(horizon)
    print(f"\n_(weekly note: {note.relative_to(repo_root())})_")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
