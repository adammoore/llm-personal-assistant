#!/usr/bin/env python3
"""monitor — the constant-companion loop (ADR-002).

Every ~2.5 min: cheap deterministic reads → diff against saved state → react to genuinely
new events (important mail, imminent meetings, deadlines) → refresh surfaces → persist state.
The watching is LLM-free; nudges reuse schedule/nudge.sh. Dedup means the *same* thing is
nudged once ever; rate-limits are generous (Adam chose chatty).

Modes:
  --once     one cycle then exit (for testing/smoke)
  --dry      compute events + what it WOULD nudge, but send nothing and refresh nothing
  --interval SECONDS  poll interval for the loop (default 150)
  --state PATH        state file override (testing)

First run seeds state silently (records what already exists without nudging).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lib.comms import ACCOUNTS, calendar_events, fetch_inbox, partition_inbox  # noqa: E402
from lib.state import (  # noqa: E402
    already_nudged, load_state, rate_state, record_nudge, repo_root, save_state,
)
from lib.taskstore import load_tasks  # noqa: E402

# Defaults (mirrored in autonomy.yaml `monitor:` for documentation).
IMMINENT_MIN = 15          # calendar: warn this many minutes ahead
SURFACE_REFRESH_MIN = 15   # re-render dashboard + PA Today at most this often
MIN_GAP_S = 30             # min seconds between nudges
HOURLY_CAP = 20            # per-hour nudge cap before coalescing
COALESCE_ABOVE = 3         # >this many fresh events in one cycle -> one summary nudge


# --- watchers: each returns list of {"key","text"} and updates state's seen-sets ----------

def watch_mail(state: dict) -> list[dict]:
    """New worth-a-look messages since last seen, per account."""
    events, seen = [], state.setdefault("seen_mail", {})
    for acct in ACCOUNTS:
        worth, _ = partition_inbox(fetch_inbox(acct["mail"]))
        known = set(seen.get(acct["id"], []))
        for m in worth:
            if m["id"] and m["id"] not in known:
                events.append({"key": f"mail:{acct['id']}:{m['id']}",
                               "text": f"✉ {m['from']}: {m['subject'][:70]} ({acct['id']})"})
        # Track current worth-a-look ids (cap the memory so it can't grow unbounded).
        seen[acct["id"]] = [m["id"] for m in worth][:200]
    return events


def watch_calendar(state: dict, now: datetime) -> list[dict]:
    """Timed events today starting within the imminent window and not yet reminded."""
    events = []
    reminded = set(state.setdefault("reminded_events", []))
    today = now.date()
    window_end = now + timedelta(minutes=IMMINENT_MIN)
    for acct in ACCOUNTS:
        for ev in calendar_events(acct["cal"], today, today):
            when = ev.get("when")
            if not when or when == "all day":
                continue
            try:
                start = datetime.fromisoformat(f"{ev.get('date', today.isoformat())}T{when}")
            except ValueError:
                continue
            if now <= start <= window_end:
                key = f"cal:{ev.get('date')}:{when}:{ev['title'][:40]}"
                if key not in reminded:
                    mins = max(1, int((start - now).total_seconds() // 60))
                    events.append({"key": key, "text": f"📅 {ev['title']} in ~{mins} min"})
                    reminded.add(key)
    state["reminded_events"] = list(reminded)[-200:]
    return events


def watch_deadlines(state: dict, now: datetime) -> list[dict]:
    """Open tasks that are due today or overdue and not yet flagged."""
    events = []
    notified = set(state.setdefault("deadline_notified", []))
    today = now.date().isoformat()
    for t in load_tasks():
        if t.get("completed") or not t.get("due_date"):
            continue
        if t["due_date"] <= today and t["id"] not in notified:
            when = "overdue" if t["due_date"] < today else "due today"
            events.append({"key": f"deadline:{t['id']}", "text": f"⏰ {t['title']} — {when}"})
            notified.add(t["id"])
    state["deadline_notified"] = list(notified)
    return events


# --- reaction ----------------------------------------------------------------------------

def _send(text: str) -> None:
    """Fire one nudge through the existing (dedup-agnostic) Signal path."""
    nudge = repo_root() / "schedule" / "nudge.sh"
    subprocess.run(["bash", str(nudge), text], check=False,
                   capture_output=True, text=True, timeout=30)


def react(state: dict, events: list[dict], now: datetime, *, dry: bool) -> list[str]:
    """Apply dedup + rate-limit, send (or in dry mode collect) nudges. Returns what was sent."""
    fresh = [e for e in events if not already_nudged(state, e["key"])]
    if not fresh:
        return []
    rate = rate_state(state, now, min_gap_s=MIN_GAP_S, hourly_cap=HOURLY_CAP)
    sent: list[str] = []

    coalesce = (len(fresh) > COALESCE_ABOVE) or not rate["gap_ok"] or not rate["under_cap"]
    if coalesce:
        text = f"🔔 {len(fresh)} things need a look — open PA Today."
        if not dry:
            _send(text)
        sent.append(text)
        for e in fresh:                    # record all so they never re-fire
            record_nudge(state, e["key"], now)
    else:
        for e in fresh:
            if not dry:
                _send(e["text"])
            record_nudge(state, e["key"], now)
            sent.append(e["text"])
    return sent


def _refresh_surfaces(state: dict, now: datetime, *, dry: bool) -> bool:
    """Re-render dashboard + PA Today at most every SURFACE_REFRESH_MIN. Returns True if done."""
    last = state.get("last_surface_refresh")
    if last:
        try:
            if now - datetime.fromisoformat(last) < timedelta(minutes=SURFACE_REFRESH_MIN):
                return False
        except ValueError:
            pass
    if not dry:
        root = repo_root()
        subprocess.run(["python3", str(root / "build_pa_dashboard.py")],
                       check=False, capture_output=True, timeout=60)
        subprocess.run(["python3", str(root / "skills/checkin-daily/push_today.py")],
                       check=False, capture_output=True, timeout=60)
    state["last_surface_refresh"] = now.isoformat(timespec="seconds")
    return True


def cycle(state: dict, now: datetime, *, dry: bool) -> dict:
    """One monitor pass. Returns a small report for logging/tests."""
    events = watch_mail(state) + watch_calendar(state, now) + watch_deadlines(state, now)
    # First run: seed silently so we don't nudge about everything that already exists.
    if not state.get("seeded"):
        state["seeded"] = True
        return {"seeded": True, "events": len(events), "sent": []}
    sent = react(state, events, now, dry=dry)
    refreshed = _refresh_surfaces(state, now, dry=dry)
    return {"seeded": False, "events": len(events), "sent": sent, "refreshed": refreshed}


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="The constant-companion monitor loop.")
    p.add_argument("--once", action="store_true", help="run a single cycle then exit")
    p.add_argument("--dry", action="store_true", help="compute + report, send/refresh nothing")
    p.add_argument("--interval", type=int, default=150, help="loop poll interval (seconds)")
    p.add_argument("--state", default=None, type=Path, help="state file override (testing)")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    while True:
        state = load_state(args.state)
        now = datetime.now()
        try:
            report = cycle(state, now, dry=args.dry)
            save_state(state, args.state)
            stamp = now.isoformat(timespec="seconds")
            if report.get("seeded"):
                print(f"{stamp}  seeded ({report['events']} items recorded, no nudges)")
            else:
                print(f"{stamp}  events={report['events']} sent={len(report['sent'])}"
                      f" refreshed={report.get('refreshed')}")
                for s in report["sent"]:
                    print(f"    → {s}")
        except Exception as exc:  # noqa: BLE001 — the loop must survive any single-cycle error
            print(f"{now.isoformat(timespec='seconds')}  cycle error (non-fatal): {exc}",
                  file=sys.stderr)
        if args.once:
            return 0
        time.sleep(max(30, args.interval))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
