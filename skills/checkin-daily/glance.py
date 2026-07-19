#!/usr/bin/env python3
"""checkin-daily glance — gather today's calendar, a prioritised inbox, and due tasks.

The read-only data-gathering half of the `checkin-daily` skill (ADR-001 §goals 1-3).
Everything here is at the *autonomous* tier: it only reads and summarises (gog for
calendar, himalaya for mail, the local task store). No sends, no writes to Google.

Real inboxes are noisy (receipts, newsletters, LinkedIn, marketing), so the inbox is
*prioritised*, not merely listed: obvious noise is counted and hidden, and only mail
"worth a look" is surfaced, capped per account. The two Gmail accounts are kept in
separate, labelled sections (ADR-001 §4) — never blended.

Output: a calm markdown glance to stdout (the skill frames it as an invitation). Also
writes/refreshes a daily-note stub at data/daily/<YYYY-MM-DD>.md for the durable trace.

Usage: python3 skills/checkin-daily/glance.py [--date YYYY-MM-DD] [--per-account 6]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lib.comms import ACCOUNTS, calendar_events, fetch_inbox, partition_inbox  # noqa: E402
from lib.taskstore import load_tasks, repo_root  # noqa: E402


def calendar_today(cal_account: str, day: date) -> list[dict]:
    """Today's events for one account (thin wrapper over the shared helper)."""
    return calendar_events(cal_account, day, day)


def inbox(mail_account: str, limit: int = 25) -> tuple[list[dict], int]:
    """Recent mail split into (worth_a_look, noise_count) via the shared lib."""
    return partition_inbox(fetch_inbox(mail_account, limit))


def due_tasks(day: date) -> list[dict]:
    """Open tasks due on/before today (overdue + today), soonest first."""
    tasks = [t for t in load_tasks() if not t.get("completed") and t.get("due_date")]
    due = [t for t in tasks if t["due_date"] <= day.isoformat()]
    return sorted(due, key=lambda t: t["due_date"])


def build_glance(day: date, per_account: int) -> str:
    """Assemble the markdown morning glance."""
    lines = [f"# Morning glance — {day.strftime('%A %-d %B %Y')}", ""]

    # Calendar, per account, kept separate.
    lines.append("## Today's calendar")
    any_events = False
    for acct in ACCOUNTS:
        evs = calendar_today(acct["cal"], day)
        if not evs:
            continue
        any_events = True
        lines.append(f"\n**{acct['id']}** ({acct['cal']})")
        for ev in evs:
            loc = f" · {ev['location'][:40]}" if ev["location"] else ""
            lines.append(f"- {ev['when']} — {ev['title']}{loc}")
    if not any_events:
        lines.append("\n_Nothing scheduled — the day is yours._")

    # Inbox, per account, prioritised.
    lines.append("\n## Inbox — worth a look")
    for acct in ACCOUNTS:
        worth, noise = inbox(acct["mail"])
        shown = worth[:per_account]
        lines.append(f"\n**{acct['id']}** ({acct['cal']})")
        if not shown:
            lines.append(f"- _nothing standing out_ ({noise} newsletters/receipts hidden)")
        else:
            for m in shown:
                dot = "•" if m["unread"] else "◦"
                lines.append(f"- {dot} {m['from']}: {m['subject'][:70]}")
            extra = len(worth) - len(shown)
            tail = f"  _(+{extra} more, {noise} noise hidden)_" if extra else \
                   f"  _({noise} noise hidden)_"
            lines.append(tail)

    # Due tasks from the local store.
    due = due_tasks(day)
    lines.append("\n## Due")
    if not due:
        lines.append("- _nothing due — no pressure_")
    else:
        for t in due:
            overdue = " (was due " + t["due_date"] + ")" if t["due_date"] < day.isoformat() else ""
            lines.append(f"- #{t['id']} {t['title']} [{t['category']}]{overdue}")

    return "\n".join(lines) + "\n"


def write_daily_note(day: date, glance: str) -> Path:
    """Write/refresh the daily note stub (durable trace); leaves intentions for the skill."""
    note = repo_root() / "data" / "daily" / f"{day.isoformat()}.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    if not note.exists():
        body = (glance + "\n## Top 3 intentions\n_(added during check-in — skippable)_\n"
                "\n## Reflection\n_(optional)_\n")
        note.write_text(body, encoding="utf-8")
    return note


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gather the daily check-in glance.")
    p.add_argument("--date", default=None, help="ISO date (default: today)")
    p.add_argument("--per-account", type=int, default=6, help="max inbox items per account")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    day = date.fromisoformat(args.date) if args.date else date.today()
    glance = build_glance(day, args.per_account)
    note = write_daily_note(day, glance)
    print(glance)
    print(f"\n_(daily note: {note.relative_to(repo_root())})_")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
