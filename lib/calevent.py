#!/usr/bin/env python3
"""calevent — turn a proposed-event into calendar fields, and manage the propose→confirm queue.

Phase 3 of event capture. The write itself (create a real Google Calendar event) is agent-only:
gog can read the calendar but not create, so creation goes through the Calendar MCP
(`mcp__claude_ai_Google_Calendar__create_event`) via the calendar-capture skill. This module is
the dependency-free glue both the daemon (serve routes: confirm/dismiss) and the agent (skill:
build fields, create, mark added) share.

Status lifecycle on each item in data/proposed_events.json:
  proposed → (Adam clicks Add) confirmed → (agent creates it) added
           → (Adam dismisses)  dismissed
Honours autonomy.yaml: modify_calendar is confirm-required — nothing here writes the calendar; the
'confirmed' status IS Adam's confirmation, which the agent then acts on.
"""

from __future__ import annotations

import fcntl
import json
import sys
from datetime import datetime, timedelta
import re
from pathlib import Path

CACHE = Path(__file__).resolve().parents[1] / "data" / "proposed_events.json"
_LOCK = CACHE.with_suffix(".lock")                         # advisory lock guarding read-modify-write
ACCOUNT = "fairresconman@gmail.com"                        # Adam's stated target calendar
_KEEP = 20                                                 # cap the queue to the most recent N rows

_PREFIXES = ("reminder:", "reminder", "appt:", "fyi:", "info:", "alert:", "notification:")
_CUT = re.compile(r"\s+(?:at\s+\d|on\s+\d|from\s+\d|call\b|tel\b|phone\b|reply\b|to cancel|"
                  r"to rearrange|to reschedule|ref\b|please\b)", re.I)
_POSTCODE = re.compile(r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}\b")


def _clean_title(snippet: str) -> tuple[str, bool]:
    """(title, is_fallback). is_fallback=True means we couldn't extract a title and used the
    generic 'Appointment' — the confirm card should flag it so Adam knows it's not from the text."""
    s = " ".join((snippet or "").split())
    low = s.lower()
    for p in _PREFIXES:
        if low.startswith(p):
            s = s[len(p):].strip(" :-")
            break
    cut = _CUT.search(s)                                   # stop before the date/time/phone tail
    if cut:
        s = s[:cut.start()].strip(" ,.-")
    if "," in s:                                           # keep the "what", drop the address tail
        s = s.split(",")[0].strip()
    return (s[:70], False) if s else ("Appointment", True)


def _location(snippet: str) -> str | None:
    m = _POSTCODE.search(snippet or "")
    if not m:
        return None
    head = snippet[:m.start()].rstrip(" ,")                # phrase before the postcode (venue)
    segs = [s.strip() for s in head.split(",") if s.strip()]
    venue = (segs[-1] if segs else head)[-40:].strip()     # last non-empty segment = the venue
    return f"{venue}, {m.group(0)}".strip(", ")


def event_fields(prop: dict) -> dict:
    """Calendar-create fields from a proposal — {title, start, end, all_day, location, description}."""
    when = prop.get("when") or {}
    start = when.get("iso") or ""
    has_time = bool(when.get("has_time"))
    try:
        s = datetime.fromisoformat(start)
        end = (s + timedelta(hours=1)).isoformat(timespec="minutes") if has_time \
            else (s + timedelta(days=1)).date().isoformat()
    except ValueError:
        end = start
    title, title_fallback = _clean_title(prop.get("snippet", ""))
    location = _location(prop.get("snippet", ""))
    # Per-field provenance: whether each value was lifted from the message or is a guess. A time
    # that didn't parse silently becomes an all-day block; a missing title becomes "Appointment";
    # a location is always a postcode-regex guess. The confirm card flags these before Adam approves.
    provenance = {
        "title": "fallback" if title_fallback else "parsed",
        "all_day": "no-time-parsed" if not has_time else "parsed",
        "location": "guessed" if location else "none",
    }
    return {"title": title,
            "start": start, "end": end, "all_day": not has_time,
            "location": location,
            "description": (prop.get("snippet") or "") + f"\n\n(captured from {prop.get('source','')}"
                           f" · {prop.get('sender','')})",
            "account": ACCOUNT, "provenance": provenance}


class _QueueCorrupt(RuntimeError):
    """The queue file exists but isn't parseable — refuse to overwrite it (don't lose data)."""


def _read_items() -> list[dict]:
    """Current queue items. Missing/empty file → []; present-but-unparseable → _QueueCorrupt.

    The distinction matters: two independent processes write this file (the dashboard on a click,
    the monitor daemon on detection). Reading a truncated/corrupt file as [] and then writing that
    back would silently erase a confirmed appointment — so a mutate raises rather than clobbers.
    """
    try:
        raw = CACHE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as e:                                   # unreadable — treat as corrupt, don't wipe
        raise _QueueCorrupt(str(e)) from e
    if not raw.strip():
        return []
    try:
        return json.loads(raw).get("items", [])
    except ValueError as e:
        raise _QueueCorrupt(str(e)) from e


def _atomic_write(items: list[dict]) -> None:
    """Write via a temp file + replace so a crash / full disk can't truncate the live file."""
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE.with_suffix(CACHE.suffix + ".tmp")
    tmp.write_text(json.dumps({"items": items}, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    tmp.replace(CACHE)


def _mutate(fn):
    """Serialize a read-modify-write across processes: hold an exclusive lock over a FRESH read,
    apply fn(items) -> (new_items, result), then write atomically. Returns result (None on corrupt).

    The lock closes the clobber window where one process reads {A}, another appends {A,B}, and the
    first writes back its stale {A} — dropping B. Both writers (dashboard, daemon) go through here.
    """
    _LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOCK, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)                     # released when the file closes
        try:
            items = _read_items()
        except _QueueCorrupt as e:
            print(f"calevent: proposed-events queue unreadable ({e}) — refusing to overwrite",
                  file=sys.stderr)
            return None
        new_items, result = fn(items)
        _atomic_write(new_items)
        return result


def _load() -> list[dict]:
    """Read-only view for callers (pending/consumers). Corrupt → [] (they only read, never write)."""
    try:
        return _read_items()
    except _QueueCorrupt:
        return []


def pending(status: str = "confirmed") -> list[dict]:
    """Proposals in a given status (default 'confirmed' — awaiting the agent to create them)."""
    return [p for p in _load() if (p.get("status") or "proposed") == status]


def set_status(key: str, status: str) -> bool:
    """Move a proposal to a new status (confirmed | dismissed | added). Returns True if found.

    Locked + atomic: re-reads under the lock so a concurrent daemon append is never clobbered.
    """
    def _fn(items):
        hit = False
        for p in items:
            if p.get("key") == key:
                p["status"] = status
                hit = True
        if not hit:
            return items, False
        # drop dismissed/added rows so the surface stays to just live proposals + confirmations
        return [p for p in items if (p.get("status") or "proposed") not in ("dismissed", "added")], True
    return bool(_mutate(_fn))


def append_proposals(records: list[dict]) -> int:
    """Merge fresh proposal records (each carrying a 'key') into the queue; return how many are new.

    The monitor daemon's write path — locked + atomic + deduped, sharing calevent's single lock so
    it can't race the dashboard. Records already have their final shape; we only dedup and cap.
    """
    if not records:
        return 0

    def _fn(items):
        have = {p.get("key") for p in items}
        added = 0
        for r in records:
            if r.get("key") in have:
                continue
            items.append(r)
            have.add(r.get("key"))
            added += 1
        return items[-_KEEP:], added
    return _mutate(_fn) or 0
