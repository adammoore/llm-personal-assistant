#!/usr/bin/env python3
"""people_discover — deeper mining of email + iMessage (via Contacts) to find real people.

seed_from_mail only skims the top ~40 worth-a-look *received* emails, so it misses everyone Adam
actually corresponds with. This digs deeper:

  - Email: received AND **sent** across both accounts (who he writes to is a strong signal),
    counted by frequency.
  - iMessage: conversation partners by message volume, resolved from phone numbers to **names**
    via the macOS Contacts store (read-only, WAL-copied like chat.db/Reminders) — that's how the
    17k-message number becomes a real person.
  - WhatsApp: not minable — OpenClaw doesn't archive history (see ADR-005 / the Matrix plan).

Candidates are classified (person/org), deduped against existing people (upsert matches on
email-else-name), and added with provenance. Read-only w.r.t. all sources.
"""

from __future__ import annotations

import re
import shutil
import sqlite3
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.comms import ACCOUNTS, _run, is_noise
from lib.people import classify_kind, load_people, save_people, upsert

_AB_DIR = Path.home() / "Library" / "Application Support" / "AddressBook" / "Sources"

# Don't add Adam himself, and skip obvious newsletter/brand display-names the noise filter misses.
_SELF = {"adam moore", "adam vials moore", "moore.adam@gmail.com", "fairresconman@gmail.com"}
_NEWSLETTERISH = re.compile(
    r"\bAI\b|rundown|newsletter|digest|daily|weekly|deals?|traders?|rocket|deepdown|"
    r"reservation|noreply|no-reply", re.IGNORECASE)


def _is_self(name: str, email: str | None) -> bool:
    return (name or "").strip().lower() in _SELF or (email or "").strip().lower() in _SELF


def _norm_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _norm_phone(s: str | None) -> str:
    """Last 10 digits — enough to match '+44 151 709 8585' against '+447931540482'-style handles."""
    d = re.sub(r"\D", "", s or "")
    return d[-10:] if len(d) >= 10 else d


def _contact_name(first: str | None, last: str | None, org: str | None) -> str:
    nm = " ".join(x for x in (first, last) if x).strip()
    return nm or (org or "").strip()


def contacts_index() -> tuple[dict, dict]:
    """(phone→name, email→name) from macOS Contacts. Empty dicts if unreadable."""
    dbs = list(_AB_DIR.glob("*/AddressBook-v22.abcddb")) if _AB_DIR.exists() else []
    phone_map: dict[str, str] = {}
    email_map: dict[str, str] = {}
    for db in dbs:
        with tempfile.TemporaryDirectory(prefix="pa_ab_") as td:
            dst = Path(td) / "ab.db"
            try:
                shutil.copy2(db, dst)
                for ext in ("-wal", "-shm"):
                    side = db.with_name(db.name + ext)
                    if side.exists():
                        shutil.copy2(side, dst.with_name(dst.name + ext))
                con = sqlite3.connect(f"file:{dst}?mode=ro", uri=True, timeout=5)
                names = {}
                for pk, f, l, org in con.execute(
                        "SELECT Z_PK, ZFIRSTNAME, ZLASTNAME, ZORGANIZATION FROM ZABCDRECORD"):
                    nm = _contact_name(f, l, org)
                    if nm:
                        names[pk] = nm
                for owner, num in con.execute(
                        "SELECT ZOWNER, ZFULLNUMBER FROM ZABCDPHONENUMBER WHERE ZFULLNUMBER IS NOT NULL"):
                    if owner in names:
                        phone_map.setdefault(_norm_phone(num), names[owner])
                try:
                    for owner, addr in con.execute(
                            "SELECT ZOWNER, ZADDRESS FROM ZABCDEMAILADDRESS WHERE ZADDRESS IS NOT NULL"):
                        if owner in names and addr:
                            email_map.setdefault(addr.strip().lower(), names[owner])
                except sqlite3.Error:
                    pass
                con.close()
            except (OSError, sqlite3.Error):
                continue
    return phone_map, email_map


def discover_email(limit: int = 200) -> dict:
    """{key: {name, email, count, sent}} across received + sent, both accounts."""
    import json
    cand: dict[str, dict] = {}

    def add(name: str, addr: str, sent: bool) -> None:
        name = (name or "").strip()
        addr = (addr or "").strip().lower()
        if not name or " " not in name or "@" in name:      # need a real 2-part display name
            return
        if _is_self(name, addr) or _NEWSLETTERISH.search(name):
            return
        key = _norm_name(name)                              # key by NAME so same person merges
        c = cand.setdefault(key, {"name": name, "email": addr or None, "count": 0, "sent": False})
        c["count"] += 1
        c["sent"] = c["sent"] or sent
        if addr and not c["email"]:
            c["email"] = addr

    for acct in ACCOUNTS:
        for folder, field, sent in (("INBOX", "from", False),
                                    ("Sent Items", "to", True), ("[Gmail]/Sent Mail", "to", True)):
            raw = _run(["himalaya", "envelope", "list", "-a", acct["mail"], "-f", folder,
                        "--page-size", str(limit), "-o", "json"])
            if not raw:
                continue
            try:
                envs = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for e in envs:
                if not sent and is_noise(e):                 # skip newsletters on the received side
                    continue
                who = e.get(field) or {}
                add(who.get("name") or "", who.get("addr") or "", sent)
    return cand


def discover_imessage(min_count: int = 8) -> list[dict]:
    """Named iMessage partners (resolved via Contacts) with ≥ min_count messages."""
    from lib import imessage as im
    if not im.available():
        return []
    phone_map, email_map = contacts_index()
    counts: dict[str, int] = defaultdict(int)
    try:
        q = ("SELECT h.id, COUNT(*) FROM message m JOIN handle h ON m.handle_id=h.ROWID "
             "GROUP BY h.id")
        for hid, c in im._connect().execute(q):
            counts[hid] = c
    except sqlite3.Error:
        return []
    out = []
    for hid, c in counts.items():
        if c < min_count:
            continue
        name = (email_map.get((hid or "").lower()) if "@" in (hid or "")
                else phone_map.get(_norm_phone(hid)))
        if name and " " in name:                            # only add resolved, real-name people
            out.append({"name": name, "email": hid if "@" in hid else None, "count": c})
    return out


def candidates(*, min_email: int = 3, min_im: int = 12) -> list[dict]:
    """Ranked, deduped NEW-person candidates not already tracked. Writes nothing.

    email: kept if ≥ min_email interactions OR written to at least twice (sent is deliberate).
    iMessage: resolved-name partners with ≥ min_im messages. Merged by name; ranked by volume.
    """
    existing = {_norm_name(p.get("name", "")) for p in load_people()}
    existing_emails = {(p.get("email") or "").lower() for p in load_people() if p.get("email")}
    merged: dict[str, dict] = {}

    def offer(name: str, email: str | None, count: int, source: str, sent: bool = False) -> None:
        key = _norm_name(name)
        if not key or key in existing:
            return
        if email and email.lower() in existing_emails:
            return
        c = merged.setdefault(key, {"name": name, "email": email, "count": 0,
                                    "sources": set(), "sent": sent})
        c["count"] += count
        c["sources"].add(source)
        c["sent"] = c["sent"] or sent
        if email and not c["email"]:
            c["email"] = email

    for c in discover_email().values():
        if c["count"] >= min_email or (c["sent"] and c["count"] >= 2):
            offer(c["name"], c["email"], c["count"], "email", c["sent"])
    from lib import imessage as im
    if im.available():
        for c in discover_imessage(min_count=min_im):
            offer(c["name"], c["email"], c["count"], "imessage")

    out = []
    for c in merged.values():
        out.append({"name": c["name"], "email": c["email"], "count": c["count"],
                    "source": "+".join(sorted(c["sources"])),
                    "kind": classify_kind(c["name"], c["email"])})
    out.sort(key=lambda x: -x["count"])
    return out


def add_people(cands: list[dict]) -> int:
    """Add the chosen candidates to the store. Returns how many were newly added."""
    people = load_people()
    before = len(people)
    for c in cands:
        ctx = "personal" if "imessage" in c.get("source", "") else "work"
        rec = upsert(people, name=c["name"], email=c.get("email"), context=ctx)
        rec.setdefault("kind", c.get("kind") or classify_kind(c["name"], c.get("email")))
        rec.setdefault("priority", "normal")
        rec["discovered"] = c.get("source", "discover")
        rec["interactions"] = max(rec.get("interactions", 0), c.get("count", 0))
    save_people(people)
    return len(people) - before


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Deeper people discovery from email + iMessage.")
    ap.add_argument("--add", action="store_true", help="write the candidates (default: preview)")
    ap.add_argument("--min-email", type=int, default=3)
    ap.add_argument("--min-im", type=int, default=12)
    args = ap.parse_args()
    cands = candidates(min_email=args.min_email, min_im=args.min_im)
    print(f"{len(cands)} new candidates (ranked by interactions):")
    for c in cands:
        badge = "🏢" if c["kind"] == "org" else "  "
        print(f"  {c['count']:>5}  {badge} {c['name'][:30]:30} [{c['source']}]")
    if args.add:
        print(f"\nadded {add_people(cands)} people.")
    else:
        print("\n(preview only — re-run with --add to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
