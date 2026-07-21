#!/usr/bin/env python3
"""state — persistent monitor state + a dedup / rate-limit ledger.

The monitor daemon (ADR-002) must remember what it has already seen and already nudged, or
it would either flood on every poll or nag about the same thing forever. This owns that
memory: `data/state.json` (git-ignored).

Shape:
    {
      "seeded": bool,                       # first run records state without nudging
      "seen_mail": {account_id: [ids]},     # mail ids already observed, per account
      "reminded_events": [event_keys],      # calendar events already reminded
      "deadline_notified": [task_ids],      # tasks already flagged due/overdue
      "nudge_ledger": {event_key: iso_ts},  # last time each event key was nudged (dedup)
      "last_surface_refresh": iso_ts|None
    }

The ledger drives two guards (see ADR-002 anti-fatigue):
  - DEDUP: a stable event key is nudged once, ever.
  - RATE-LIMIT: a min gap between nudges + a per-hour cap (generous, since Adam chose chatty).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def state_path() -> Path:
    return repo_root() / "data" / "state.json"


def _blank() -> dict:
    return {
        "seeded": False,
        "seen_mail": {},
        "reminded_events": [],
        "deadline_notified": [],
        "nudge_ledger": {},
        "last_surface_refresh": None,
    }


def load_state(path: Path | None = None) -> dict:
    """Load state, tolerating a missing/corrupt file by returning a fresh blank."""
    path = path or state_path()
    if not path.exists():
        return _blank()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _blank()
    # Fill any missing keys so older/partial files stay usable.
    base = _blank()
    base.update({k: v for k, v in data.items() if k in base})
    return base


def save_state(state: dict, path: Path | None = None) -> None:
    """Persist state atomically (temp file + replace)."""
    path = path or state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def already_nudged(state: dict, event_key: str) -> bool:
    """Dedup: has this exact event ever been nudged?"""
    return event_key in state.get("nudge_ledger", {})


def _sent_within(state: dict, now: datetime, window: timedelta) -> list[datetime]:
    """Timestamps of nudges sent within `window` of now (for rate-limiting)."""
    out = []
    for iso in state.get("nudge_ledger", {}).values():
        try:
            ts = datetime.fromisoformat(iso)
        except ValueError:
            continue
        if now - ts <= window:
            out.append(ts)
    return out


def rate_state(state: dict, now: datetime, *, min_gap_s: int = 30,
               hourly_cap: int = 20) -> dict:
    """Return {'gap_ok': bool, 'under_cap': bool} for the current moment."""
    recent = _sent_within(state, now, timedelta(hours=1))
    last = max(recent, default=None)
    gap_ok = last is None or (now - last) >= timedelta(seconds=min_gap_s)
    return {"gap_ok": gap_ok, "under_cap": len(recent) < hourly_cap}


def record_nudge(state: dict, event_key: str, now: datetime) -> None:
    """Mark an event key as nudged at `now`."""
    state.setdefault("nudge_ledger", {})[event_key] = now.isoformat(timespec="seconds")
