#!/usr/bin/env python3
"""activity — one normalized stream over tasks, calendar, mail, and work files.

Salvaged from Adam's idea-tracker "Activity Hub": every heterogeneous thing the PA
knows about — a task, a calendar event, a mail worth a look, a recently-touched work
file — is flattened into a single `Activity` shape so it can be sorted, filtered, and
rendered as one timeline. This is the practical seed of the ZigZag "associative trails"
idea: put everything on one plane first, discover the trails between them later.

Read-only and defensive throughout. Every builder reuses the existing lib modules
(`lib.taskstore`, `lib.comms`, `lib.onedrive`) and tolerates missing fields — a source
that fails or returns nothing simply contributes no activities, never an exception.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

# Allow `python3 lib/activity.py` (run as a script) to resolve the `lib` package by
# putting the repo root — one level up from this file — on the import path first.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.comms import ACCOUNTS, calendar_events, fetch_inbox, partition_inbox  # noqa: E402
from lib.onedrive import recent_files  # noqa: E402
from lib.taskstore import load_tasks  # noqa: E402

# The four sources an Activity can originate from (kept as a tuple for cheap validation).
SOURCES = ("task", "calendar", "mail", "file")


@dataclass
class Activity:
    """One normalized item on the unified stream.

    Fields:
      source    — one of SOURCES ("task" | "calendar" | "mail" | "file").
      type      — finer kind within the source (e.g. task category, "event", "mail").
      timestamp — ISO string (date or datetime) the item is anchored to, or None.
      title     — one-line human label.
      theme     — free project tag (e.g. "Case", "House"), or None.
      priority  — "high" | "normal" | "low" for tasks, else None.
      url       — a link/opener if one exists, or None.
      meta      — source-specific extras (never relied on by the renderer).
    """

    source: str
    type: str
    timestamp: str | None
    title: str
    theme: str | None = None
    priority: str | None = None
    url: str | None = None
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Return a plain dict (JSON-friendly), preserving field order."""
        return {
            "source": self.source,
            "type": self.type,
            "timestamp": self.timestamp,
            "title": self.title,
            "theme": self.theme,
            "priority": self.priority,
            "url": self.url,
            "meta": self.meta,
        }


def _sort_key(activity: Activity) -> str:
    """Sort key for newest/soonest-first: timestamp desc, undated items last.

    Descending sort puts the largest (latest / furthest-future) ISO string first; an
    empty string for a missing timestamp naturally sinks to the bottom of that order.
    """
    return activity.timestamp or ""


def from_tasks() -> list[Activity]:
    """Open tasks as activities, anchored to due date (falling back to created_at)."""
    activities: list[Activity] = []
    for task in load_tasks():
        if task.get("completed"):
            continue
        # Prefer the due date as the anchor; fall back to when it was captured.
        timestamp = task.get("due_date") or task.get("created_at")
        activities.append(
            Activity(
                source="task",
                type=task.get("category") or "Other",
                timestamp=timestamp,
                title=task.get("title") or "(untitled task)",
                theme=task.get("theme"),
                priority=task.get("priority"),
                url=None,
                meta={
                    "id": task.get("id"),
                    "due_date": task.get("due_date"),
                    # Tolerate fields the store may not carry on every record.
                    "energy": task.get("energy"),
                    "estimate_min": task.get("estimate_min"),
                    "task_source": task.get("source"),
                },
            )
        )
    return activities


def from_calendar(days: int = 14) -> list[Activity]:
    """Upcoming events across both calendars for the next `days`, as activities."""
    today = date.today()
    end = today + timedelta(days=days)
    activities: list[Activity] = []
    for acct in ACCOUNTS:
        for ev in calendar_events(acct.get("cal", ""), today, end):
            day = ev.get("date") or ""
            when = ev.get("when") or ""
            # Compose an ISO-ish anchor: "YYYY-MM-DD HH:MM" when timed, else the date.
            timestamp = f"{day} {when}".strip() if when and when != "all day" else day
            location = ev.get("location") or ""
            title = ev.get("title") or "(no title)"
            activities.append(
                Activity(
                    source="calendar",
                    type="event",
                    timestamp=timestamp or None,
                    title=title,
                    theme=None,
                    priority=None,
                    url=None,
                    meta={
                        "account": acct.get("id"),
                        "when": when,
                        "location": location,
                    },
                )
            )
    return activities


def from_messages() -> list[Activity]:
    """Mail worth a look across both inboxes (noise filtered out), as activities."""
    activities: list[Activity] = []
    for acct in ACCOUNTS:
        worth, _noise = partition_inbox(fetch_inbox(acct.get("mail", "")))
        for msg in worth:
            sender = msg.get("from") or "(unknown)"
            subject = msg.get("subject") or "(no subject)"
            activities.append(
                Activity(
                    source="mail",
                    type="mail",
                    timestamp=msg.get("date") or None,
                    title=f"{sender}: {subject}",
                    theme=None,
                    priority=None,
                    url=None,
                    meta={
                        "account": acct.get("id"),
                        "id": msg.get("id"),
                        "unread": msg.get("unread"),
                    },
                )
            )
    return activities


def from_files(days: int = 14) -> list[Activity]:
    """Recently-touched work files (metadata only) as activities."""
    activities: list[Activity] = []
    for entry in recent_files(days=days):
        folder = entry.get("folder") or ""
        root = entry.get("root") or ""
        where = folder if folder and folder != "." else root
        activities.append(
            Activity(
                source="file",
                type="file",
                timestamp=entry.get("modified") or None,
                title=entry.get("name") or "(unnamed file)",
                theme=where or None,
                priority=None,
                url=None,
                meta={"folder": folder, "root": root},
            )
        )
    return activities


def unified(days: int = 14) -> list[Activity]:
    """Merge all four sources into one stream, newest/soonest-first.

    Each builder is independently defensive, so one failing source never sinks the
    whole stream — it simply contributes nothing.
    """
    activities: list[Activity] = []
    activities.extend(from_tasks())
    activities.extend(from_calendar(days))
    activities.extend(from_messages())
    activities.extend(from_files(days))
    activities.sort(key=_sort_key, reverse=True)
    return activities


def main() -> int:
    """Print a short unified list — a quick smoke test of the stream."""
    stream = unified()
    if not stream:
        print("(no activity — empty stream)")
        return 0
    print(f"Unified activity — {len(stream)} items")
    for a in stream[:25]:
        stamp = (a.timestamp or "—")[:16].ljust(16)
        print(f"  {stamp}  [{a.source:8}] {a.title[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
