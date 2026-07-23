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
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lib.comms import ACCOUNTS, calendar_events, fetch_inbox, partition_inbox  # noqa: E402
from lib.state import (  # noqa: E402
    already_nudged, load_state, mark_retracted, pending_mail_nudges, rate_state,
    record_mail_nudge, record_nudge, repo_root, save_state,
)
from lib.imessage import captures as imessage_captures  # noqa: E402
from lib.taskstore import add_task, load_tasks  # noqa: E402

# Defaults (mirrored in autonomy.yaml `monitor:` for documentation).
IMMINENT_MIN = 15          # calendar: warn this many minutes ahead
SURFACE_REFRESH_MIN = 15   # re-render dashboard + PA Today at most this often
MIN_GAP_S = 30             # min seconds between nudges
HOURLY_CAP = 20            # per-hour nudge cap before coalescing
COALESCE_ABOVE = 3         # >this many fresh events in one cycle -> one summary nudge
MAX_RETRACT_PER_CYCLE = 5  # cap stale-nudge retractions per pass (belt-and-braces vs. surges)

# nudge.sh prints "✅ Sent via Signal. Message ID: <id>" — this pulls the <id> back out so we
# can remote-delete that exact message if the email it flagged later disappears.
_MSG_ID_RE = re.compile(r"Message ID:\s*(\S+)")


# --- watchers: each returns list of {"key","text"} and updates state's seen-sets ----------

def watch_mail(state: dict, present: dict | None = None) -> list[dict]:
    """New worth-a-look messages since last seen, per account.

    If `present` is given it is filled with {account_id: {all current inbox ids}} — the
    retraction step uses it to notice when a previously-nudged email has vanished.
    """
    events, seen = [], state.setdefault("seen_mail", {})
    for acct in ACCOUNTS:
        inbox = fetch_inbox(acct["mail"])
        worth, _ = partition_inbox(inbox)
        if present is not None:
            # Every id currently in the inbox (not just worth-a-look ones): an email that is
            # merely read still shows here, so it won't be mistaken for archived/deleted.
            present[acct["id"]] = {m["id"] for m in inbox if m["id"]}
        known = set(seen.get(acct["id"], []))
        for m in worth:
            if m["id"] and m["id"] not in known:
                events.append({"key": f"mail:{acct['id']}:{m['id']}",
                               "text": f"✉ {m['from']}: {m['subject'][:70]} ({acct['id']})",
                               "account": acct["id"], "mail_id": m["id"],
                               "subject": m["subject"]})
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

def _send(text: str) -> str | None:
    """Fire one nudge through the existing (dedup-agnostic) Signal path.

    Returns the sent message's id (parsed from nudge.sh stdout) so a mail nudge can later be
    retracted, or None if nothing usable came back (unconfigured no-op, send failure, etc.).
    """
    nudge = repo_root() / "schedule" / "nudge.sh"
    try:
        proc = subprocess.run(["bash", str(nudge), text], check=False,
                              capture_output=True, text=True, timeout=30)
    except (subprocess.SubprocessError, OSError):
        return None
    m = _MSG_ID_RE.search(proc.stdout or "")
    msg_id = m.group(1) if m else None
    # "unknown" is what the backend prints for a dry/unconfigured send — not retractable.
    return msg_id if msg_id and msg_id != "unknown" else None


def _signal_target() -> str | None:
    """Resolve the Signal recipient a retraction must be addressed to.

    nudge.sh owns the actual send config; we only need the target for `openclaw message
    delete`. Prefer an explicit env override, else scrape it out of schedule/nudge.env.
    """
    for var in ("MONITOR_SIGNAL_TARGET", "SIGNAL_TO"):
        val = os.environ.get(var)
        if val and val.strip():
            return val.strip()
    try:
        text = (repo_root() / "schedule" / "nudge.env").read_text(encoding="utf-8")
    except OSError:
        return None
    for pat in (r"--target\s+(\+?\d+)", r"SIGNAL_TO=['\"]?(\+?\d+)"):
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None


def _retract(rec: dict) -> bool:
    """Best-effort retract one stale mail nudge. Never raises.

    Primary path is a genuine remote delete: `openclaw message delete` maps onto signal-cli's
    `remoteDelete`, so the nudge actually vanishes from Adam's phone. If that handle is missing
    or the delete doesn't take, we fall back to ONE short follow-up note so he at least knows
    the item is handled (a note can't unsend, hence it is the fallback, not the default).
    """
    target, msg_id = rec.get("target"), rec.get("msg_id")
    if target and msg_id:
        try:
            proc = subprocess.run(
                ["openclaw", "message", "delete", "--channel", "signal",
                 "--target", target, "--message-id", msg_id],
                check=False, capture_output=True, text=True, timeout=30)
            if proc.returncode == 0:
                return True
        except (subprocess.SubprocessError, OSError):
            pass  # fall through to the note
    subj = (rec.get("subject") or "that email").strip()[:60]
    _send(f"↩︎ earlier: '{subj}' is handled — no action needed.")
    return True


def retract_stale(state: dict, present: dict, now: datetime, *, dry: bool) -> list[str]:
    """Retract mail nudges whose email has disappeared from its inbox since we flagged it.

    "Gone" = the nudged envelope id is no longer among the account's current inbox ids
    (archived/deleted/moved). We only judge an account whose fetch returned something this
    cycle: an empty/failed himalaya read looks identical to an emptied inbox, so skipping it
    avoids mass-retracting on a transient blip (documented limitation).
    """
    retracted: list[str] = []
    for key, rec in pending_mail_nudges(state).items():
        if len(retracted) >= MAX_RETRACT_PER_CYCLE:
            break
        current = present.get(rec.get("account"))
        if not current:                       # not fetched / empty / failed -> don't judge
            continue
        if rec.get("mail_id") in current:     # still in the inbox -> leave the nudge be
            continue
        if dry:                               # report intent only; never touch Signal/state
            retracted.append(key)
            continue
        try:
            _retract(rec)
        except Exception as exc:  # noqa: BLE001 — one bad retraction must not kill the loop
            print(f"    retract error (non-fatal) {key}: {exc}", file=sys.stderr)
        # Tombstone regardless of outcome so we never hammer a message we can't remove.
        mark_retracted(state, key, now)
        retracted.append(key)
    return retracted


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
            msg_id = None
            if not dry:
                msg_id = _send(e["text"])
            record_nudge(state, e["key"], now)
            # Capture a retraction handle for individually-sent MAIL nudges only. (Coalesced
            # nudges cover many events in one message, so retracting on a single vanished
            # email would be wrong — those are intentionally not tracked.)
            if msg_id and e["key"].startswith("mail:"):
                record_mail_nudge(state, e["key"], msg_id=msg_id, target=_signal_target(),
                                  account=e.get("account", ""), mail_id=e.get("mail_id", ""),
                                  subject=e.get("subject", ""), now=now)
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
        # Refresh the Apple Reminders mirror (fast, ~0.1s) before rebuilding so the dashboard
        # reflects anything captured via Siri / the Reminders app / the WhatsApp agent.
        subprocess.run(["python3", str(root / "lib/reminders.py")],
                       check=False, capture_output=True, timeout=30)
        subprocess.run(["python3", str(root / "build_pa_dashboard.py")],
                       check=False, capture_output=True, timeout=60)
        subprocess.run(["python3", str(root / "skills/checkin-daily/push_today.py")],
                       check=False, capture_output=True, timeout=60)
    state["last_surface_refresh"] = now.isoformat(timespec="seconds")
    return True


def capture_imessage(state: dict, *, dry: bool) -> list[str]:
    """Phone capture: self-sent iMessages prefixed 'todo/pa/capture/task …' become tasks."""
    last = state.get("last_imessage_rowid", 0)
    caps, top = imessage_captures(last)
    state["last_imessage_rowid"] = top
    done = []
    for c in caps:
        text = c.get("text", "").strip()
        if not text:
            continue
        if not dry:
            add_task(text, source="imessage")
        done.append(text)
    return done


def cycle(state: dict, now: datetime, *, dry: bool) -> dict:
    """One monitor pass. Returns a small report for logging/tests."""
    present: dict[str, set] = {}   # {account_id: current inbox ids} — feeds retraction
    events = (watch_mail(state, present) + watch_calendar(state, now)
              + watch_deadlines(state, now))
    # First run: seed silently so we don't nudge about everything that already exists
    # (and set the iMessage baseline so history isn't captured).
    if not state.get("seeded"):
        state["seeded"] = True
        state["last_imessage_rowid"] = imessage_captures(0)[1]
        return {"seeded": True, "events": len(events), "sent": []}
    captured = capture_imessage(state, dry=dry)
    sent = react(state, events, now, dry=dry)
    retracted = retract_stale(state, present, now, dry=dry)
    refreshed = _refresh_surfaces(state, now, dry=dry)
    if captured and not dry:
        # rebuild the dashboard now so the new task shows, and confirm on Signal.
        subprocess.run(["python3", str(repo_root() / "build_pa_dashboard.py")],
                       check=False, capture_output=True, timeout=60)
        _send(f"✓ captured {len(captured)}: " + "; ".join(captured)[:90])
    return {"seeded": False, "events": len(events), "sent": sent, "captured": captured,
            "refreshed": refreshed, "retracted": retracted}


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
                retracted = report.get("retracted", [])
                captured = report.get("captured", [])
                print(f"{stamp}  events={report['events']} sent={len(report['sent'])}"
                      f" captured={len(captured)} retracted={len(retracted)}"
                      f" refreshed={report.get('refreshed')}")
                for s in report["sent"]:
                    print(f"    → {s}")
                for c in captured:
                    print(f"    ⌨ captured: {c}")
                for k in retracted:
                    print(f"    ↩ retracted {k}")
        except Exception as exc:  # noqa: BLE001 — the loop must survive any single-cycle error
            print(f"{now.isoformat(timespec='seconds')}  cycle error (non-fatal): {exc}",
                  file=sys.stderr)
        if args.once:
            return 0
        time.sleep(max(30, args.interval))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
