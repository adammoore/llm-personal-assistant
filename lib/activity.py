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

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Allow `python3 lib/activity.py` (run as a script) to resolve the `lib` package by
# putting the repo root — one level up from this file — on the import path first.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.comms import ACCOUNTS  # noqa: E402
from lib.glance import load as glance_load  # noqa: E402
from lib.onedrive import recent_files  # noqa: E402
from lib.taskstore import load_tasks  # noqa: E402

# The sources an Activity can originate from (kept as a tuple for cheap validation).
SOURCES = ("task", "calendar", "mail", "file", "work")

# Compact snapshot of the Westminster/Enact work surfaces, written by skills/work-pull
# (`pull.py --cache`). Read defensively — it may be absent, stale, or mark Chrome down.
_WORK_CACHE = Path(__file__).resolve().parents[1] / "data" / "work_cache.json"


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


def _sort_key(activity: Activity) -> tuple[int, str]:
    """Sort key for SOONEST-first: dated items ascending by timestamp, undated items last.

    The leading flag (0 = has a timestamp, 1 = none) keeps undated items at the bottom
    regardless of the empty string sorting first; within dated items the ISO timestamp
    sorts ascending so the nearest date/time comes first.
    """
    ts = activity.timestamp or ""
    return (0, ts) if ts else (1, "")


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
    """Upcoming events across both calendars, as activities — from the glance cache (no network)."""
    events_by_acct = glance_load().get("events", {})
    activities: list[Activity] = []
    for acct in ACCOUNTS:
        for ev in events_by_acct.get(acct.get("id", ""), []):
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
    """Mail worth a look across both inboxes (noise filtered), as activities — from glance cache."""
    mail_by_acct = glance_load().get("mail", {})
    activities: list[Activity] = []
    for acct in ACCOUNTS:
        worth = mail_by_acct.get(acct.get("id", ""), {}).get("worth", [])
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


# Map a work surface id onto the Activity source that best fits its glyph/filtering.
_WORK_SOURCE = {"mail": "mail", "calendar": "calendar"}


def from_work_cache(path: Path = _WORK_CACHE) -> list[Activity]:
    """Westminster/Enact work surfaces (from the work-pull cache) as activities.

    Defensive: a missing/unreadable/malformed cache, or one marking Chrome down, simply
    yields nothing. Each surface with a snippet becomes one Activity anchored to the cache's
    `at` timestamp, titled by its label plus a short snippet.
    """
    activities: list[Activity] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return activities
    if not isinstance(data, dict) or not data.get("up"):
        return activities
    at = data.get("at") or None
    for src in data.get("sources") or []:
        if not isinstance(src, dict):
            continue
        text = (src.get("text") or "").strip()
        if not text:
            continue
        label = src.get("label") or "Work"
        # First line of the snippet, collapsed, as a glance.
        snippet = " ".join(text.split())[:56]
        activities.append(
            Activity(
                source=_WORK_SOURCE.get(src.get("id"), "work"),
                type="work",
                timestamp=at,
                title=f"{label}: {snippet}" if snippet else label,
                theme="Work",
                priority=None,
                url=None,
                meta={"surface": src.get("id"), "cache_at": at},
            )
        )
    return activities


def unified(days: int = 14) -> list[Activity]:
    """Merge all sources into one stream, newest/soonest-first.

    Each builder is independently defensive, so one failing source never sinks the
    whole stream — it simply contributes nothing.
    """
    activities: list[Activity] = []
    activities.extend(from_tasks())
    activities.extend(from_calendar(days))
    activities.extend(from_messages())
    activities.extend(from_files(days))
    activities.extend(from_work_cache())
    activities.sort(key=_sort_key)
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
