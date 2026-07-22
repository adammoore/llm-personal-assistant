#!/usr/bin/env python3
"""monica — read Adam's self-hosted Monica personal CRM via its REST API.

Adds the *person* dimension (ADR-004): upcoming birthdays and "stay in touch" nudges, and
(later) person-as-a-thread. Read-only. Config lives in a git-ignored `monica.env` at the repo
root: `MONICA_URL=https://...` and `MONICA_TOKEN=<personal access token>`.

Defensive by design: no config, an unreachable server, or an unexpected shape → returns empty,
never raises. Field mappings follow Monica API v1 (`/api/contacts`) but are read tolerantly
with `.get`, so they degrade gracefully and are easy to verify against a live instance.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _config() -> tuple[str, str] | None:
    """Return (base_url, token) from monica.env, or None if not configured."""
    env = repo_root() / "monica.env"
    if not env.exists():
        return None
    url = token = ""
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("MONICA_URL="):
            url = line.split("=", 1)[1].strip().strip('"').rstrip("/")
        elif line.startswith("MONICA_TOKEN="):
            token = line.split("=", 1)[1].strip().strip('"')
    return (url, token) if url and token else None


def configured() -> bool:
    return _config() is not None


def _get(path: str) -> dict | None:
    """GET {base}/api/{path} with the bearer token; None on any failure."""
    cfg = _config()
    if not cfg:
        return None
    base, token = cfg
    req = urllib.request.Request(
        f"{base}/api/{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def contacts(limit: int = 100) -> list[dict]:
    """All contacts (best-effort), normalised to {name, birthdate, last_activity}."""
    data = _get(f"contacts?limit={limit}")
    if not data or "data" not in data:
        return []
    out = []
    for c in data.get("data", []):
        name = c.get("complete_name") or " ".join(
            filter(None, [c.get("first_name"), c.get("last_name")])) or "(unnamed)"
        dates = ((c.get("information") or {}).get("dates") or {})
        birth = (dates.get("birthdate") or {}).get("date")  # ISO or None
        out.append({
            "id": c.get("id"),
            "name": name,
            "birthdate": (birth or "")[:10] or None,
            "last_activity": ((c.get("information") or {}).get("career") or {}) and
                             c.get("last_activity_together"),  # tolerated if absent
        })
    return out


def _next_birthday(birth: str, today: date) -> int | None:
    """Days until the next occurrence of a MM-DD birthday, or None."""
    try:
        d = date.fromisoformat(birth)
    except ValueError:
        return None
    try:
        nxt = d.replace(year=today.year)
    except ValueError:                       # 29 Feb → treat as 1 Mar
        nxt = date(today.year, 3, 1)
    if nxt < today:
        nxt = nxt.replace(year=today.year + 1)
    return (nxt - today).days


def upcoming_birthdays(days: int = 30, today: date | None = None) -> list[dict]:
    """Contacts with a birthday within `days`, soonest first."""
    today = today or date.today()
    out = []
    for c in contacts():
        if not c.get("birthdate"):
            continue
        n = _next_birthday(c["birthdate"], today)
        if n is not None and n <= days:
            out.append({"name": c["name"], "in_days": n})
    return sorted(out, key=lambda x: x["in_days"])


def main() -> int:
    if not configured():
        print("Monica not configured — see MONICA_SETUP.md")
        return 0
    for b in upcoming_birthdays():
        print(f"🎂 {b['name']} — in {b['in_days']}d")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
