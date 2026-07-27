#!/usr/bin/env python3
"""events — detect appointment/event candidates in incoming messages (Phase 1 + 2).

Read-only DETECTION so the monitor can PROPOSE a calendar entry — never write one. This honours
autonomy.yaml exactly: `propose_calendar` is autonomous-flagged; `modify_calendar` (writing a real
event) is confirm-required and lives in the create step (Phase 3), not here.

`detect_candidates(messages)` scans each message for an appointment CUE + a parseable date/time and
returns candidates with a normalised `when`. `on_calendar(when)` roughly dedups against the glance
calendar cache so we only propose things Adam doesn't already have. Date parsing prefers the
`dateparser` package if present (best for "next Tue at 3"), else a dependency-free regex fallback
covering the common SMS-reminder formats; UK day-first on ambiguous D/M.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

# Cues that signal a real scheduled thing (not chit-chat). Kept broad but not marketing-y.
_CUES = ("appointment", "appt", "booked", "confirmed", "scheduled", "reschedul", "your visit",
         "consultation", "clinic", "surgery", "review on", "assessment", "hearing", "session on",
         "reminder", "reserved", "booking", "see you on", "due on", "attend", "meeting on")

# Marketing / noise — suppress to cut false positives.
_NOISE = ("book now", "unsubscribe", "% off", "offer ends", "sale ends", "shop now", "deal ends",
          "limited time", "flash sale", "voucher", "discount code")

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_WEEKDAYS = {d: i for i, d in enumerate(
    ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])}

_GLANCE = Path(__file__).resolve().parents[1] / "data" / "glance_cache.json"


def _as_dt(ref) -> datetime:
    if isinstance(ref, datetime):
        return ref
    if isinstance(ref, str) and ref:
        try:
            return datetime.fromisoformat(ref[:19])
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    return datetime.strptime(ref[:19], fmt)
                except ValueError:
                    continue
    return datetime.now()


def _find_time(text: str) -> tuple[int, int] | None:
    """First clock time in the text → (hour, minute), or None."""
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\b", text, re.I)
    if m:
        h = int(m.group(1)) % 12
        if m.group(3).lower() == "p":
            h += 12
        return h, int(m.group(2) or 0)
    m = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)   # 24h
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _find_date(text: str, base: datetime):
    """First plausible future date in the text → date-bearing datetime (00:00), or None."""
    low = text.lower()
    # ISO YYYY-MM-DD
    m = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # D Mon [Year]  /  Mon D
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})\b(?:\s+(20\d{2}))?", low)
    if m and m.group(2)[:3] in _MONTHS:
        return _mk(int(m.group(1)), _MONTHS[m.group(2)[:3]], m.group(3), base)
    m = re.search(r"\b([a-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:\s+(20\d{2}))?", low)
    if m and m.group(1)[:3] in _MONTHS:
        return _mk(int(m.group(2)), _MONTHS[m.group(1)[:3]], m.group(3), base)
    # D/M[/Y] — UK day-first
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", text)
    if m:
        yr = m.group(3)
        yr = (2000 + int(yr)) if yr and len(yr) == 2 else (int(yr) if yr else None)
        return _mk(int(m.group(1)), int(m.group(2)), yr, base)
    # today / tomorrow
    if "tomorrow" in low:
        return (base + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if "today" in low or "tonight" in low:
        return base.replace(hour=0, minute=0, second=0, microsecond=0)
    # weekday name → next occurrence (respect "next")
    for name, idx in _WEEKDAYS.items():
        if re.search(rf"\b{name}[a-z]*\b", low):
            ahead = (idx - base.weekday()) % 7
            if ahead == 0 or "next " + name in low:
                ahead += 7 if "next " in low else (0 if ahead else 7)
            return (base + timedelta(days=ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
    return None


def _mk(day: int, month: int, year, base: datetime):
    """Build a date; infer the year (roll to next year if the date already passed)."""
    try:
        y = int(year) if year else base.year
        dt = datetime(y, month, day)
        if not year and dt.date() < base.date() - timedelta(days=1):
            dt = datetime(y + 1, month, day)
        return dt
    except (ValueError, TypeError):
        return None


def parse_when(text: str, ref) -> dict | None:
    """Extract {iso, has_time, display} from free text, or None if no confident date."""
    base = _as_dt(ref)
    try:
        from dateparser.search import search_dates
        found = search_dates(text, settings={"RELATIVE_BASE": base, "PREFER_DATES_FROM": "future",
                                              "DATE_ORDER": "DMY"})
        for _t, dt in (found or []):
            if dt.date() >= base.date() - timedelta(days=1):
                has_time = dt.hour != 0 or dt.minute != 0
                return _when(dt, has_time)
    except Exception:  # noqa: BLE001 — dateparser optional; regex fallback below
        pass
    d = _find_date(text, base)
    if not d:
        return None
    t = _find_time(text)
    if t:
        d = d.replace(hour=t[0], minute=t[1])
    return _when(d, bool(t))


def _when(dt: datetime, has_time: bool) -> dict:
    disp = dt.strftime("%a %-d %b" + (" %H:%M" if has_time else ""))
    return {"iso": dt.isoformat(timespec="minutes"), "has_time": has_time, "display": disp}


def detect_candidates(messages: list[dict], now: datetime | None = None) -> list[dict]:
    """Messages that look like appointment reminders → candidates with a parsed `when`.

    Each message is a dict with at least `text`; optional `date` (ISO, the reference for relative
    dates), `sender`, `source`. Returns the message enriched with `when` + `snippet`.
    """
    out = []
    for m in messages:
        text = (m.get("text") or "").strip()
        low = text.lower()
        if not text or any(n in low for n in _NOISE):
            continue
        if not any(c in low for c in _CUES):
            continue
        when = parse_when(text, m.get("date") or now)
        if not when:
            continue
        out.append({**m, "when": when, "snippet": " ".join(text.split())[:140]})
    return out


def on_calendar(when: dict, path: Path | None = None) -> bool:
    """Rough dedup: is there already a glance event on that day (within ~3h if timed)?"""
    try:
        iso = when["iso"]
        want = datetime.fromisoformat(iso)
    except (KeyError, ValueError, TypeError):
        return False
    try:
        data = json.loads((path or _GLANCE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    day = want.date().isoformat()
    for evs in (data.get("events") or {}).values():
        for e in evs:
            if (e.get("date") or "")[:10] != day:
                continue
            if not when.get("has_time"):
                return True                                # same-day event exists → assume covered
            ew = e.get("when") or ""
            mt = re.match(r"(\d{1,2}):(\d{2})", ew)
            if not mt:
                return True
            ev = want.replace(hour=int(mt.group(1)), minute=int(mt.group(2)))
            if abs((ev - want).total_seconds()) <= 3 * 3600:
                return True
    return False


def candidate_key(c: dict) -> str:
    """Stable-ish dedup key for a proposal (sender + day + first words)."""
    who = (c.get("sender") or c.get("source") or "").lower()[:20]
    day = (c.get("when", {}).get("iso") or "")[:10]
    head = re.sub(r"\W+", "", (c.get("snippet") or "").lower())[:24]
    return f"{who}:{day}:{head}"
