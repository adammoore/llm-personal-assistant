#!/usr/bin/env python3
"""inbox — one unified message stream across venues, each tagged with a derived context.

The ADHD-PA goal is "one coordinated view over everything, then help focus". Messages arrive in
different **venues** (accounts/channels) but belong to different **contexts** (life domains), and
the two don't line up one-to-one — so we keep both as separate facet dimensions:

  venue  = where it physically arrived   (moore.adam Gmail, fairresconman Gmail, iMessage, …)
  context = the life domain it's about    (personal, consulting, legal, local-authority, medical, work)

Adam's mapping, from his own words:
  - fairresconman was his consulting inbox but is now also the main venue for **legal**
  - moore.adam carries **personal**, **local-authority**, and **medical**
  - Westminster is **work**

Context is *derived* (a predictable lens, not a stored field) from venue + sender/subject, mirroring
the dashboard's existing _ctx approach. Read-only: this only reads what lib.comms / lib.imessage read.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import comms  # noqa: E402
from lib import imessage as im  # noqa: E402

# Venue labels shown in the UI (channel/account, not domain).
VENUE_MAIL = {"personal": "moore.adam", "fairres": "fairresconman"}

# --- Context derivation cues (lowercased substring match on sender+subject/text) -------------
_MEDICAL = ("nhs", "gp ", "surgery", "hospital", "doctor", "patient", "prescription",
            "health", "clinic", "@nhs", "dentist", "physio")
_LOCAL_AUTHORITY = ("council", ".gov.uk", "gov.uk", "social care", "social work", "safeguard",
                    "mash", "children's services", "childrens services", "local authority",
                    "sefton", "iro ", "cp plan", "core group")
_LEGAL = ("solicitor", "court", "barrister", "chambers", " law", "legal", "hearing", "tribunal",
          "injunction", " order", "family court", "cps", "urn", "lv26", "900769", "police",
          "henry williams", "isabella", "jmw", "form e", "fdr", "hay & kilner", "hay and kilner",
          # case-specific: names, refs and professionals (from the project context) → legal/case
          "vials moore", "gwen", "isaac", "cora", "lv26p70571", "lv26f00570", "25001035948",
          "26000175134", "liverpool county", "videoremotehearings", "cvp link", "hayley",
          "theresa dearn", "medical records", "private & confidential")


def _ctx_for(venue_id: str, haystack: str) -> str:
    """Derive the life-domain context for a message. Venue sets the default; content refines it."""
    h = haystack.lower()
    if venue_id == "fairres":
        return "legal" if any(k in h for k in _LEGAL) else "consulting"
    if venue_id == "personal":
        if any(k in h for k in _MEDICAL):
            return "medical"
        if any(k in h for k in _LOCAL_AUTHORITY):
            return "local-authority"
        return "personal"
    if venue_id == "imessage":
        # A phone message can still be about the case/LA — let content pull it out of "personal".
        if any(k in h for k in _LEGAL):
            return "legal"
        if any(k in h for k in _LOCAL_AUTHORITY):
            return "local-authority"
        return "personal"
    return "personal"


def _mail_messages(limit: int) -> list[dict]:
    out = []
    for acct in comms.ACCOUNTS:
        venue = VENUE_MAIL.get(acct["id"], acct["id"])
        worth, _ = comms.partition_inbox(comms.fetch_inbox(acct["mail"], limit=limit))
        for e in worth:
            hay = f'{e["from"]} {e["subject"]}'
            out.append({
                "venue": venue, "venue_id": acct["id"], "channel": "mail",
                "context": _ctx_for(acct["id"], hay),
                "who": e["from"], "subject": e["subject"], "text": "",
                "date": e["date"], "unread": e["unread"],
            })
    return out


import re  # noqa: E402

# iMessage automated/short-code senders: numeric short codes (e.g. "443" voicemail), branded
# alpha-senders, and one-time-passcode bodies — not real conversations, hidden from the glance.
_IM_NOISE_SENDER = re.compile(r"^\d{3,6}$|login|verify|code$|no.?reply", re.IGNORECASE)
_IM_NOISE_BODY = re.compile(
    r"\b\d{4,8} is your|security code|verification code|one[- ]time|new message in your mailbox",
    re.IGNORECASE)


def _im_is_noise(who: str, text: str) -> bool:
    # Automated senders/OTP bodies, plus the shared mail marketing filter applied to the text.
    if _IM_NOISE_SENDER.search(who or "") or _IM_NOISE_BODY.search(text or ""):
        return True
    return bool(comms.NOISE.search(f"{who} {text}"))


def _imessage_messages(days: int, limit: int) -> list[dict]:
    out = []
    for m in im.recent(days=days, limit=limit):
        if m["from_me"]:
            continue  # inbox = things sent TO Adam
        text = m["text"]
        if _im_is_noise(m["who"], text):
            continue
        out.append({
            "venue": "iMessage", "venue_id": "imessage", "channel": "imessage",
            "context": _ctx_for("imessage", f'{m["who"]} {text}'),
            "who": m["who"], "subject": text[:80], "text": text,
            "date": (m["date"] or "")[:10], "unread": False,
        })
    return out


def unified(mail_limit: int = 25, imessage_days: int = 14, imessage_limit: int = 40) -> list[dict]:
    """The whole stream, newest first: [{venue, venue_id, channel, context, who, subject, text, date, unread}]."""
    msgs = _mail_messages(mail_limit) + _imessage_messages(imessage_days, imessage_limit)
    msgs.sort(key=lambda m: m.get("date") or "", reverse=True)
    return msgs


def facet_counts(msgs: list[dict]) -> dict:
    """{'venue': {name: n}, 'context': {name: n}} for the facet chips."""
    venues: dict[str, int] = {}
    contexts: dict[str, int] = {}
    for m in msgs:
        venues[m["venue"]] = venues.get(m["venue"], 0) + 1
        contexts[m["context"]] = contexts.get(m["context"], 0) + 1
    return {"venue": venues, "context": contexts}


def write_cache(path: Path | None = None) -> dict:
    """Snapshot the unified inbox for the dashboard. Shape: {at, items, facets}."""
    import json
    from datetime import datetime
    path = path or (Path(__file__).resolve().parents[1] / "data" / "inbox_cache.json")
    msgs = unified()
    data = {"at": datetime.now().isoformat(timespec="seconds"),
            "items": msgs, "facets": facet_counts(msgs)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def main() -> int:
    if "--cache" in sys.argv:
        d = write_cache()
        print(f"wrote inbox cache: {len(d['items'])} messages")
        return 0
    msgs = unified()
    fc = facet_counts(msgs)
    print(f"{len(msgs)} messages")
    print("venues:", ", ".join(f"{k}={v}" for k, v in sorted(fc["venue"].items())))
    print("contexts:", ", ".join(f"{k}={v}" for k, v in sorted(fc["context"].items())))
    for m in msgs[:20]:
        flag = "•" if m["unread"] else " "
        print(f"  {flag} {m['date']}  [{m['venue']}/{m['context']}]  {m['who'][:22]:22}  {m['subject'][:44]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
