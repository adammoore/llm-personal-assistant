#!/usr/bin/env python3
"""people — a light local people/relationship layer (ADR-004 option A1).

The person dimension without a server: a JSON store the PA reads/writes, seedable from real
mail contacts so it populates itself. Gives the People card its "reconnect" nudges and
birthdays, and is the anchor for person-as-a-thread later. If Monica is ever self-hosted,
`lib/monica.py` can enrich this — the two are complementary.

Store (git-ignored, private): data/people.json — a list of:
    {id, name, email, context, relationship, birthday, last_seen, notes, themes}
Only `name` is required; everything else is optional/accreted (incremental formalization).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def store_path() -> Path:
    return repo_root() / "data" / "people.json"


def load_people(path: Path | None = None) -> list[dict]:
    path = path or store_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def save_people(people: list[dict], path: Path | None = None) -> None:
    path = path or store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(people, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _next_id(people: list[dict]) -> int:
    return max((int(p.get("id", 0)) for p in people), default=0) + 1


def _key(name: str, email: str | None) -> str:
    return (email or "").lower() or name.strip().lower()


def upsert(people: list[dict], *, name: str, email: str | None = None,
           context: str = "personal", last_seen: str | None = None) -> dict:
    """Add or update a person (matched by email, else name). Returns the record."""
    k = _key(name, email)
    for p in people:
        if _key(p.get("name", ""), p.get("email")) == k:
            if email and not p.get("email"):
                p["email"] = email
            if last_seen and last_seen > (p.get("last_seen") or ""):
                p["last_seen"] = last_seen
            return p
    rec = {"id": _next_id(people), "name": name, "email": email, "context": context,
           "relationship": None, "birthday": None, "last_seen": last_seen,
           "notes": None, "themes": []}
    people.append(rec)
    return rec


# Senders that aren't people — reuse the mail noise sense: skip role/no-reply addresses.
_NON_PERSON = ("no-reply", "noreply", "notifications", "mailer", "bounce", "donotreply",
               "support@", "info@", "team@", "hello@", "updates@", "digest")


def seed_from_mail(path: Path | None = None) -> int:
    """Populate/refresh people from real mail senders across both accounts. Returns new count."""
    import sys
    sys.path.insert(0, str(repo_root()))
    from lib.comms import ACCOUNTS, fetch_inbox, is_noise, partition_inbox  # noqa: E402
    people = load_people(path)
    before = len(people)
    for acct in ACCOUNTS:
        worth, _ = partition_inbox(fetch_inbox(acct["mail"], limit=40))
        ctx = "work" if acct["id"] == "fairres" else "personal"
        for m in worth:
            if is_noise(m.get("_raw") or {}):                 # newsletters/marketing → not a person
                continue
            raw = (m.get("_raw") or {}).get("from") or {}
            name, addr = (raw.get("name") or m.get("from") or "").strip(), (raw.get("addr") or "")
            # Require a real two-part name (filters single-token brands like "AINews"),
            # a non-role address, and no obvious brand markers.
            if not name or " " not in name or "@" in name:
                continue
            if any(tok in (addr or name).lower() for tok in _NON_PERSON):
                continue
            upsert(people, name=name, email=addr or None, context=ctx,
                   last_seen=(m.get("date") or "")[:10] or None)
    save_people(people, path)
    return len(people) - before


def upcoming_birthdays(days: int = 45, today: date | None = None) -> list[dict]:
    """People with a birthday within `days` (birthday stored ISO or MM-DD)."""
    today = today or date.today()
    out = []
    for p in load_people():
        b = p.get("birthday")
        if not b:
            continue
        try:
            md = date.fromisoformat(b) if len(b) > 5 else date.fromisoformat(f"2000-{b}")
        except ValueError:
            continue
        try:
            nxt = md.replace(year=today.year)
        except ValueError:
            nxt = date(today.year, 3, 1)
        if nxt < today:
            nxt = nxt.replace(year=today.year + 1)
        n = (nxt - today).days
        if n <= days:
            out.append({"name": p["name"], "in_days": n})
    return sorted(out, key=lambda x: x["in_days"])


def reconnect_due(days: int = 30, today: date | None = None) -> list[dict]:
    """People not seen (no mail from them) in over `days` — gentle reconnect candidates."""
    today = today or date.today()
    out = []
    for p in load_people():
        seen = p.get("last_seen")
        if not seen:
            continue
        try:
            gap = (today - date.fromisoformat(seen[:10])).days
        except ValueError:
            continue
        if gap >= days:
            out.append({"name": p["name"], "days": gap, "context": p.get("context")})
    return sorted(out, key=lambda x: -x["days"])


def main() -> int:
    n = seed_from_mail()
    print(f"people: {len(load_people())} total ({n:+d} from this sync)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
