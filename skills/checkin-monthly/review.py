#!/usr/bin/env python3
"""checkin-monthly review — the month in one calm picture: what changed, what's ahead.

The read-only data-gathering half of the `checkin-monthly` skill (ADR-001 build-order §6).
Everything here is at the *autonomous* tier: it only reads and summarises the local task
store (lib.taskstore) and both calendars (lib.comms). No sends, no writes to Google.

Where the daily glance is a firehose-dampener for *today*, this steps back a level:
  - WHAT CHANGED — a task-store summary (open vs done, by category) with small wins named,
    briefly. Never a debt ledger; done work is acknowledged, undone work is not itemised.
  - MONTH AHEAD — calendar highlights for the next ~30 days, both accounts kept separate.
  - CATEGORY CLEANUP — open tasks carrying no due date, grouped by category: candidates to
    schedule or gently drop (the skill offers, never forces).

Output: a calm markdown monthly review to stdout (the skill frames it as an invitation).
Also writes a monthly-note stub at data/monthly/<YYYY-MM>.md as the durable trace, with
sections for goals review, what changed, and one reflection.

Usage: python3 skills/checkin-monthly/review.py [--month YYYY-MM] [--ahead-days 30]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lib.comms import ACCOUNTS, calendar_events  # noqa: E402
from lib.taskstore import CATEGORIES, load_tasks, repo_root  # noqa: E402

# How many calendar highlights to surface per account — a glance, not the whole diary.
MAX_HIGHLIGHTS = 12


def task_summary(tasks: list[dict]) -> dict:
    """Open vs done counts, broken down by the fixed category order.

    Returns {category: {"open": n, "done": n}} plus a top-level "_total" tally, so the
    caller can render a stable, category-ordered picture without re-counting.
    """
    summary: dict = {c: {"open": 0, "done": 0} for c in CATEGORIES}
    total = {"open": 0, "done": 0}
    for t in tasks:
        # Unknown/legacy categories fold into "Other" so nothing is silently dropped.
        cat = t.get("category") if t.get("category") in summary else "Other"
        bucket = "done" if t.get("completed") else "open"
        summary[cat][bucket] += 1
        total[bucket] += 1
    summary["_total"] = total
    return summary


def done_tasks(tasks: list[dict]) -> list[dict]:
    """Completed tasks — the small wins, acknowledged briefly (never a debt ledger)."""
    return [t for t in tasks if t.get("completed")]


def undated_open(tasks: list[dict]) -> dict:
    """Open tasks with no due date, grouped by category (cleanup candidates).

    Returns {category: [task, ...]} in the fixed category order; empty groups omitted.
    These are the "schedule it or let it go?" items — the skill offers, never forces.
    """
    grouped: dict = {}
    for cat in CATEGORIES:
        group = [
            t for t in tasks
            if not t.get("completed") and not t.get("due_date")
            and (t.get("category") if t.get("category") in CATEGORIES else "Other") == cat
        ]
        if group:
            grouped[cat] = sorted(group, key=lambda t: t["id"])
    return grouped


def month_highlights(cal_account: str, start: date, end: date) -> list[dict]:
    """Notable events in [start, end] for one account, capped to a glance.

    Thin, forgiving wrapper over the shared helper: on any fetch failure it returns []
    (a check-in must never hard-fail), and it caps the list so the month reads as
    highlights, not a wall of every recurring standup.
    """
    events = calendar_events(cal_account, start, end)
    # Already date-ordered by gog; cap for calm. The count of any remainder is reported.
    return events[:MAX_HIGHLIGHTS]


def build_review(month: str, today: date, ahead_days: int) -> str:
    """Assemble the markdown monthly review."""
    tasks = load_tasks()
    lines = [f"# Monthly review — {month}", ""]

    # WHAT CHANGED — the task store, stepped back a level.
    summary = task_summary(tasks)
    total = summary["_total"]
    lines.append("## What changed")
    lines.append(
        f"\n{total['open']} open · {total['done']} done, across the task store."
    )
    for cat in CATEGORIES:
        counts = summary[cat]
        if counts["open"] == 0 and counts["done"] == 0:
            continue
        lines.append(f"- **{cat}** — {counts['open']} open, {counts['done']} done")

    # Small wins — named briefly, warmly. Not a to-do audit.
    wins = done_tasks(tasks)
    if wins:
        lines.append("\n**Small wins** (nice — these are done):")
        for t in wins:
            lines.append(f"- #{t['id']} {t['title']} [{t['category']}]")

    # MONTH AHEAD — calendar highlights, both accounts, kept separate.
    ahead_end = today + timedelta(days=ahead_days)
    lines.append(f"\n## Month ahead — next {ahead_days} days")
    any_events = False
    for acct in ACCOUNTS:
        evs = month_highlights(acct["cal"], today, ahead_end)
        if not evs:
            continue
        any_events = True
        lines.append(f"\n**{acct['id']}** ({acct['cal']})")
        for ev in evs:
            loc = f" · {ev['location'][:40]}" if ev["location"] else ""
            lines.append(f"- {ev['date']} {ev['when']} — {ev['title']}{loc}")
    if not any_events:
        lines.append("\n_Nothing notable on the horizon — room to breathe._")

    # CATEGORY CLEANUP — open, undated tasks: schedule or let go?
    cleanup = undated_open(tasks)
    lines.append("\n## Category cleanup — undated open tasks")
    if not cleanup:
        lines.append("\n_Everything open has a date — nothing loose to tidy._")
    else:
        lines.append("\n_Candidates to give a date, or to gently let go — your call:_")
        for cat, group in cleanup.items():
            lines.append(f"\n**{cat}**")
            for t in group:
                lines.append(f"- #{t['id']} {t['title']}")

    return "\n".join(lines) + "\n"


def write_monthly_note(month: str, review: str) -> Path:
    """Write/refresh the monthly note stub (durable trace); leaves prompts for the skill.

    Mirrors the daily glance's note pattern: create-once, never clobber. The stub carries
    a goals-review section, the machine-built "what changed" snapshot, and one reflection
    line — the skill fills these in with only what Adam offers.
    """
    note = repo_root() / "data" / "monthly" / f"{month}.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    if not note.exists():
        # Drop the review's own "# Monthly review" title so it doesn't double up under the
        # note's H1; what remains already opens with its own "## What changed" section.
        snapshot = review.split("\n", 2)[-1].lstrip("\n")
        body = (
            f"# Monthly review — {month}\n\n"
            "## Goals review\n_(added during check-in — skippable)_\n\n"
            + snapshot + "\n"
            "## Reflection\n_(optional — one line is plenty)_\n"
        )
        note.write_text(body, encoding="utf-8")
    return note


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gather the monthly check-in review.")
    p.add_argument("--month", default=None, help="month as YYYY-MM (default: current)")
    p.add_argument("--ahead-days", type=int, default=30, help="calendar horizon in days")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    today = date.today()
    # --month drives the header + note filename; the calendar horizon is anchored on today.
    month = args.month if args.month else today.strftime("%Y-%m")
    review = build_review(month, today, args.ahead_days)
    note = write_monthly_note(month, review)
    print(review)
    print(f"\n_(monthly note: {note.relative_to(repo_root())})_")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
