#!/usr/bin/env python3
"""comms — shared read-only plumbing over gog (calendar) and himalaya (mail).

One home for the account list, the inbox noise heuristic, and the fetch helpers, so every
skill that reads calendar/mail (`checkin-daily`, `comms-triage`, weekly/monthly, quarterly)
behaves identically and the two Gmail accounts are always handled the same way.

Everything here is READ-ONLY (autonomous tier). Nothing sends, drafts, or mutates Google.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import date

# Canonical accounts (also declared in autonomy.yaml comms.accounts).
# id = label shown to Adam; cal = gog account; mail = himalaya account.
ACCOUNTS = [
    {"id": "personal", "cal": "moore.adam@gmail.com", "mail": "moore-adam"},
    {"id": "fairres", "cal": "fairresconman@gmail.com", "mail": "fairresconman"},
]

# Coarse noise heuristic — hits on sender name/addr or subject mark an item low-signal.
# Deliberately conservative: it is better to surface a borderline item than to hide a real
# one, so the skill's model judgement makes the final call on what remains.
NOISE = re.compile(
    r"no[-_]?reply|newsletter|digest|unsubscribe|receipt|invoice|statement|linkedin|"
    r"\d+%\s*off|\bsale\b|promo|webinar|marketing|notifications?@|mailer|bounce|"
    r"quora|deals?\b|e-?newsletter|talent (network|pipeline)|boating|"
    # unambiguous marketing phrasing (safe: unlikely in real personal/work correspondence)
    r"don'?t miss|price drop|trial (has )?ended|getaway|travel hack|"
    r"limited time|last chance|exclusive interview|expires? (soon|tonight)|"
    # more marketing/transactional broadcast patterns
    r"\breward\b|unlocked|treat drop|win your|credit check|instant access|"
    r"updates? to your|your .* account will be deleted|view your .* update|"
    r"create shared|new ways to build|t&cs?\b|turn up rates|book(ing)?\.com|"
    r"rightmove|moneysupermarket|skypark|directloan|costa|"
    # one-time-passcodes / automated verification (safe to hide from a glance)
    r"\b\d{4,8} is your|security code|verification code|one[- ]time (pass)?code|\bOTP\b",
    re.IGNORECASE,
)


def _run(cmd: list[str], timeout: int = 25) -> str:
    """Run a command, returning stdout ('' on any failure — reads must never crash)."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.stdout if out.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def is_noise(env: dict) -> bool:
    """True if an envelope looks like a newsletter/receipt/marketing/social item."""
    frm = env.get("from", {}) or {}
    hay = " ".join([frm.get("name") or "", frm.get("addr") or "", env.get("subject") or ""])
    return bool(NOISE.search(hay))


def fetch_inbox(mail_account: str, limit: int = 25) -> list[dict]:
    """Recent envelopes for one account via himalaya, normalised.

    Returns [{id, from, subject, date, unread}], newest first, or [] on any failure.
    """
    raw = _run(["himalaya", "envelope", "list", "-a", mail_account,
                "--page-size", str(limit), "-o", "json"])
    if not raw:
        return []
    try:
        envs = json.loads(raw)
    except json.JSONDecodeError:
        return []
    out = []
    for e in envs:
        frm = e.get("from", {}) or {}
        out.append({
            "id": e.get("id", ""),
            "from": frm.get("name") or frm.get("addr") or "(unknown)",
            "subject": (e.get("subject") or "(no subject)").strip(),
            "date": (e.get("date") or "")[:10],
            "unread": "Seen" not in (e.get("flags") or []),
            # keep the raw envelope so callers can re-check noise without refetching
            "_raw": e,
        })
    return out


def partition_inbox(envs: list[dict]) -> tuple[list[dict], int]:
    """Split envelopes into (worth_a_look, noise_count)."""
    worth = [e for e in envs if not is_noise(e["_raw"])]
    return worth, len(envs) - len(worth)


def calendar_events(cal_account: str, start: date, end: date) -> list[dict]:
    """Events in [start, end] for one account via gog.

    Returns [{when, title, location}] where `when` is HH:MM or 'all day'.
    """
    raw = _run(["gog", "-a", cal_account, "calendar", "events", "list",
                "--from", start.isoformat(), "--to", end.isoformat(), "--json"])
    if not raw:
        return []
    try:
        events = json.loads(raw).get("events", [])
    except json.JSONDecodeError:
        return []
    out = []
    for ev in events:
        s = ev.get("start", {})
        when = s.get("dateTime", "") or s.get("date", "")
        label = when[11:16] if "T" in when else "all day"
        out.append({"when": label, "title": ev.get("summary", "(no title)"),
                    "location": (ev.get("location") or "").strip(),
                    "date": when[:10]})
    return out
