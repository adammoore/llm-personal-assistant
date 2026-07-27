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

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

CACHE = Path(__file__).resolve().parents[1] / "data" / "proposed_events.json"
ACCOUNT = "fairresconman@gmail.com"                        # Adam's stated target calendar

_PREFIXES = ("reminder:", "reminder", "appt:", "fyi:", "info:", "alert:", "notification:")
_CUT = re.compile(r"\s+(?:at\s+\d|on\s+\d|from\s+\d|call\b|tel\b|phone\b|reply\b|to cancel|"
                  r"to rearrange|to reschedule|ref\b|please\b)", re.I)
_POSTCODE = re.compile(r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}\b")


def _clean_title(snippet: str) -> str:
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
    return (s or "Appointment")[:70]


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
    return {"title": _clean_title(prop.get("snippet", "")),
            "start": start, "end": end, "all_day": not has_time,
            "location": _location(prop.get("snippet", "")),
            "description": (prop.get("snippet") or "") + f"\n\n(captured from {prop.get('source','')}"
                           f" · {prop.get('sender','')})",
            "account": ACCOUNT}


def _load() -> list[dict]:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8")).get("items", [])
    except (OSError, ValueError):
        return []


def _save(items: list[dict]) -> None:
    CACHE.write_text(json.dumps({"items": items}, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")


def pending(status: str = "confirmed") -> list[dict]:
    """Proposals in a given status (default 'confirmed' — awaiting the agent to create them)."""
    return [p for p in _load() if (p.get("status") or "proposed") == status]


def set_status(key: str, status: str) -> bool:
    """Move a proposal to a new status (confirmed | dismissed | added). Returns True if found."""
    items = _load()
    hit = False
    for p in items:
        if p.get("key") == key:
            p["status"] = status
            hit = True
    if hit:
        # drop dismissed/added rows so the surface stays to just live proposals + confirmations
        _save([p for p in items if (p.get("status") or "proposed") not in ("dismissed", "added")])
    return hit
