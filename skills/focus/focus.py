#!/usr/bin/env python3
"""focus — a single-theme (or single-priority) view of everything relevant.

The complement to the central-overview dashboard: where the overview shows everything,
`focus` collapses to one thing so Adam can go deep — that theme's tasks, plus the upcoming
dates and messages that mention it. Optionally pushes the view to the phone as a synced
"Focus" Apple Note and/or a short Signal summary.

Read-only except the optional note/Signal push (both PA-owned surfaces). Never sends mail,
never writes into CIDER.

Usage:
    focus.py Enact                    # tasks + related dates/messages for theme "Enact"
    focus.py --priority high          # everything high-priority, across themes
    focus.py Case --push-note --signal
"""

from __future__ import annotations

import argparse
import html
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lib.applenotes import set_note  # noqa: E402
from lib.comms import ACCOUNTS, calendar_events, fetch_inbox, partition_inbox  # noqa: E402
from lib.taskstore import load_tasks, priority_rank, repo_root  # noqa: E402

HORIZON_DAYS = 21


def _match_task(t: dict, theme: str | None, priority: str | None) -> bool:
    """A task is in focus if its theme matches (or the title mentions it) and priority fits."""
    if priority and t.get("priority") != priority:
        return False
    if not theme:
        return True
    tl = theme.lower()
    return (t.get("theme") or "").lower() == tl or tl in t["title"].lower()


def gather(theme: str | None, priority: str | None, today: date) -> dict:
    """Collect focused tasks, related dates, and related messages."""
    tasks = [t for t in load_tasks()
             if not t.get("completed") and _match_task(t, theme, priority)]
    tasks.sort(key=lambda t: (priority_rank(t), t.get("due_date") or "9999", t["id"]))

    # Dates/messages have no theme field, so match on the theme keyword (skip if none).
    dates, messages = [], []
    if theme:
        tl = theme.lower()
        end = today + timedelta(days=HORIZON_DAYS)
        for acct in ACCOUNTS:
            for ev in calendar_events(acct["cal"], today, end):
                if tl in ev["title"].lower():
                    dates.append({**ev, "account": acct["id"]})
            worth, _ = partition_inbox(fetch_inbox(acct["mail"]))
            for m in worth:
                if tl in (m["from"] + " " + m["subject"]).lower():
                    messages.append({**m, "account": acct["id"]})
        dates.sort(key=lambda e: (e.get("date") or "", e.get("when") or ""))
    return {"tasks": tasks, "dates": dates, "messages": messages}


def _label(theme: str | None, priority: str | None) -> str:
    if theme and priority:
        return f"{theme} · {priority} priority"
    if theme:
        return theme
    return f"{priority} priority" if priority else "everything"


def render_markdown(data: dict, theme: str | None, priority: str | None, today: date) -> str:
    """Human-readable focused view."""
    lines = [f"# Focus — {_label(theme, priority)}", f"_{today.strftime('%A %-d %B %Y')}_", ""]
    lines.append(f"## Tasks ({len(data['tasks'])})")
    if not data["tasks"]:
        lines.append("_None — nothing on this right now._")
    for t in data["tasks"]:
        flag = "‼ " if t.get("priority") == "high" else ""
        due = f" — due {t['due_date']}" if t.get("due_date") else ""
        lines.append(f"- {flag}#{t['id']} {t['title']} [{t['category']}]{due}")
    if theme:
        lines.append(f"\n## Related dates ({len(data['dates'])})")
        for e in data["dates"] or []:
            when = e.get("date", "")
            if e.get("when") and e["when"] != "all day":
                when += " " + e["when"]
            lines.append(f"- {when} — {e['title']}  _{e['account']}_")
        if not data["dates"]:
            lines.append("_None in the next 3 weeks._")
        lines.append(f"\n## Related messages ({len(data['messages'])})")
        for m in data["messages"] or []:
            lines.append(f"- {m['from']}: {m['subject'][:70]}  _{m['account']}_")
        if not data["messages"]:
            lines.append("_None standing out._")
    return "\n".join(lines) + "\n"


def _note_html(data: dict, theme: str | None, priority: str | None, today: date) -> str:
    esc = html.escape
    p = [f"<div><b>Focus — {esc(_label(theme, priority))}</b></div>",
         f"<div>{esc(today.strftime('%A %-d %B %Y'))}</div><div><br></div>"]
    p.append(f"<div><b>Tasks ({len(data['tasks'])})</b></div>")
    for t in data["tasks"] or []:
        flag = "‼ " if t.get("priority") == "high" else ""
        due = f" — due {esc(t['due_date'])}" if t.get("due_date") else ""
        p.append(f"<div>&nbsp;&nbsp;☐ {flag}{esc(t['title'])}{due}</div>")
    if not data["tasks"]:
        p.append("<div>&nbsp;&nbsp;Nothing on this right now.</div>")
    if theme:
        p.append(f"<div><br></div><div><b>Dates ({len(data['dates'])})</b></div>")
        for e in data["dates"] or []:
            p.append(f"<div>&nbsp;&nbsp;{esc(e.get('date',''))} — {esc(e['title'])}</div>")
        p.append(f"<div><br></div><div><b>Messages ({len(data['messages'])})</b></div>")
        for m in data["messages"] or []:
            p.append(f"<div>&nbsp;&nbsp;{esc(m['from'])}: {esc(m['subject'][:60])}</div>")
    return "".join(p)


def _signal_summary(data: dict, theme: str | None, priority: str | None) -> str:
    highs = sum(1 for t in data["tasks"] if t.get("priority") == "high")
    top = data["tasks"][0]["title"] if data["tasks"] else "nothing queued"
    extra = f", {highs} high" if highs else ""
    return f"🎯 Focus: {_label(theme, priority)} — {len(data['tasks'])} task(s){extra}. Next: {top}."


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A single-theme/priority focus view.")
    p.add_argument("theme", nargs="?", default=None, help="theme/project to focus on")
    p.add_argument("--priority", default=None, choices=["high", "normal", "low"])
    p.add_argument("--push-note", action="store_true", help="write a synced 'Focus' Apple Note")
    p.add_argument("--signal", action="store_true", help="send a short Signal summary")
    p.add_argument("--date", default=None, help="ISO date (default today)")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.theme and not args.priority:
        print("focus: give a theme (e.g. 'Enact') or --priority high", file=sys.stderr)
        return 2
    today = date.fromisoformat(args.date) if args.date else date.today()
    data = gather(args.theme, args.priority, today)
    print(render_markdown(data, args.theme, args.priority, today))

    if args.push_note:
        ok = set_note(f"Focus — {_label(args.theme, args.priority)}",
                      _note_html(data, args.theme, args.priority, today))
        print(f"_(Focus note pushed: {ok})_")
    if args.signal:
        nudge = repo_root() / "schedule" / "nudge.sh"
        subprocess.run(["bash", str(nudge), _signal_summary(data, args.theme, args.priority)],
                       check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
