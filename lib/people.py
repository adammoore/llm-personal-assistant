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
import re
from datetime import date
from pathlib import Path

# ── Classification: is this entry a person, or an institution/business? ──────────────────────
# Not a value judgement (an org can matter more than a person) — just a type, so the People view
# can distinguish "Isabella Martin" from "Liverpool County, Family". Auto-guessed on seed,
# overridable by hand (set_kind). Org cues: legal/institutional words, a comma'd name, digits,
# or an institutional email domain.
_ORG_TOKENS = (
    "ltd", "llp", "limited", "inc", "plc", "& co", "council", "court", "nhs", "university",
    "college", "school", "bank", "insurance", "services", "service", "team", "solicitor",
    "solicitors", "chambers", "centre", "center", "clinic", "surgery", "hospital", "group",
    "trust", "society", "association", "department", "office", "gov", "hmrc", "dwp", "company",
    "academy", "county", "practice", "partnership", "foundation", "institute", "agency",
    "bureau", "committee", "board", "union", "charity", "pharmacy", "ltd.", "co.",
    "notification", "notifications", "newsletter", "cinema", "digest", "church",
)
_CONNECTORS = {"at", "from", "on", "the", "and", "of", "for", "with", "via", "by", "&"}
_INST_DOMAINS = (".gov.uk", ".nhs.uk", ".ac.uk", ".gov", ".org.uk", ".sch.uk", ".police.uk")


def _looks_personal(name: str) -> bool:
    """A clean 2-3 token title-case name with no connector words — 'Hayley McCabe', 'CJ Woodford'."""
    toks = name.split()
    return (2 <= len(toks) <= 3
            and all(t.isalpha() and t[:1].isupper() for t in toks)
            and not any(t.lower() in _CONNECTORS for t in toks))


def classify_kind(name: str, email: str | None = None) -> str:
    """Best-effort 'person' | 'org' from the name/email. Overridable by hand (set_kind).

    The NAME wins over the domain: a plausible personal name is a person even when they email
    from an institution (a council social worker is still a person, not the council).
    """
    n = (name or "").strip()
    low = n.lower()
    if "," in n:                                            # "Liverpool County, Family"
        return "org"
    if any(re.search(r"\b" + re.escape(t) + r"\b", low) for t in _ORG_TOKENS):
        return "org"
    if any(ch.isdigit() for ch in n) or "." in n:          # brands/handles: "Video.Li", "443"
        return "org"
    if _looks_personal(n):                                  # name signal beats the domain
        return "person"
    dom = (email or "").split("@")[-1].lower()
    if dom.endswith(_INST_DOMAINS):
        return "org"
    return "org" if len(n.split()) != 2 else "person"       # multi-word non-name → likely a brand


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
           "kind": classify_kind(name, email), "priority": "normal",
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
    from lib.comms import ACCOUNTS, fetch_inbox, is_noise, partition_inbox
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


def _birthday_in_days(p: dict, today: date) -> int | None:
    b = p.get("birthday")
    if not b:
        return None
    try:
        md = date.fromisoformat(b) if len(b) > 5 else date.fromisoformat(f"2000-{b}")
    except ValueError:
        return None
    try:
        nxt = md.replace(year=today.year)
    except ValueError:
        return None
    if nxt < today:
        nxt = nxt.replace(year=today.year + 1)
    return (nxt - today).days


def attention_score(p: dict, today: date | None = None, *, pinned: bool = False) -> tuple[int, str]:
    """How much a person 'deserves attention' now — same 0-100+ scale as tasks. Returns (score, reason).

    Deliberately parallel to the task attention model: pins dominate, then the manual priority
    lever (which stays), then situational pulls — a long silence with someone you track, or a
    birthday bearing down. Returns the single strongest reason for the UI to show.
    """
    today = today or date.today()
    s, reason = 0, ""
    if pinned:
        s += 100
        reason = "pinned"
    prio = (p.get("priority") or "normal")
    s += {"high": 25, "normal": 0, "low": -10}.get(prio, 0)
    if prio == "high" and not reason:
        reason = "high priority"
    # Reconnect pull: a growing nag once silence passes ~30 days (capped so it can't dominate).
    seen = p.get("last_seen")
    if seen:
        try:
            gap = (today - date.fromisoformat(seen[:10])).days
            if gap >= 30:
                s += min(gap // 7, 10) * 3
                if not reason:
                    reason = f"not heard {gap}d"
        except ValueError:
            pass
    # Birthday bearing down.
    bd = _birthday_in_days(p, today)
    if bd is not None and bd <= 30:
        s += 20 if bd <= 7 else 8
        if not reason or bd <= 7:
            reason = f"🎂 {bd}d"
    return s, (reason or prio)


def ranked_people(pinned_names: set | None = None, today: date | None = None) -> list[dict]:
    """All people with their attention score + reason, most-deserving first."""
    today = today or date.today()
    pinned_names = pinned_names or set()
    out = []
    for p in load_people():
        sc, reason = attention_score(p, today, pinned=p.get("name") in pinned_names)
        out.append({**p, "kind": p.get("kind") or classify_kind(p.get("name", ""), p.get("email")),
                    "priority": p.get("priority") or "normal",
                    "_score": sc, "_reason": reason,
                    "_pinned": p.get("name") in pinned_names})
    out.sort(key=lambda x: -x["_score"])
    return out


def _find(people: list[dict], person_id) -> dict | None:
    try:
        pid = int(person_id)
    except (TypeError, ValueError):
        return None
    return next((p for p in people if int(p.get("id", -1)) == pid), None)


def set_kind(person_id, kind: str, path: Path | None = None) -> bool:
    """Manually set a person's kind ('person' | 'org'). Returns True if changed."""
    if kind not in ("person", "org"):
        return False
    people = load_people(path)
    p = _find(people, person_id)
    if not p:
        return False
    p["kind"] = kind
    save_people(people, path)
    return True


_PRIO_CYCLE = {"low": "normal", "normal": "high", "high": "low"}


def cycle_priority(person_id, path: Path | None = None) -> str | None:
    """Cycle a person's priority low→normal→high→low. Returns the new value."""
    people = load_people(path)
    p = _find(people, person_id)
    if not p:
        return None
    p["priority"] = _PRIO_CYCLE.get(p.get("priority") or "normal", "high")
    save_people(people, path)
    return p["priority"]


def classify_all(path: Path | None = None) -> int:
    """Backfill kind + priority on every stored person (idempotent). Returns count touched."""
    people = load_people(path)
    touched = 0
    for p in people:
        if not p.get("kind"):
            p["kind"] = classify_kind(p.get("name", ""), p.get("email"))
            touched += 1
        if not p.get("priority"):
            p["priority"] = "normal"
            touched += 1
    if touched:
        save_people(people, path)
    return touched


def main() -> int:
    n = seed_from_mail()
    classify_all()
    print(f"people: {len(load_people())} total ({n:+d} from this sync)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
