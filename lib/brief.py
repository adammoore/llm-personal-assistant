#!/usr/bin/env python3
"""brief — the situational companion brief that fronts the dashboard.

Not a tracking panel: a short, warm orientation of Adam's situation *right now* plus the 2-3
things that most deserve his attention — ranked by importance, NOT by the clock. It's the
"where am I / what's the next move" a good assistant gives, generated from the same local data
the cards show.

How: gather the situation (time of day, today's fixed points, what's pinned/overdue/due, mail
worth attention, reminders), score everything for *attention* (pinned/overdue/high-priority/
case-or-work weigh heaviest), and let `claude -p` (headless, like lib.mailsummary) write a
2-4 sentence brief + next moves. Cached to data/brief_cache.json and refreshed periodically —
render reads the cache instantly. A deterministic fallback keeps it working if claude is absent.

Guardrail: this is Adam's *private* view — it may surface case/work items plainly, but never
generates legal work-product, analysis, or clinical labels. Orientation, not advocacy.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.pins import load_pins
from lib.taskstore import load_tasks, repo_root

_CASE_WORK = ("case", "court", "fdr", "hearing", "family", "legal", "enact", "zigzag",
              "notch8", "westminster", "work")


def _cache() -> Path:
    return repo_root() / "data" / "brief_cache.json"


def load_brief() -> dict | None:
    """Cached {brief, moves, at} or None."""
    try:
        return json.loads(_cache().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _due_state(due: str | None, today: date) -> str:
    if not due:
        return "none"
    try:
        d = date.fromisoformat(due)
    except ValueError:
        return "none"
    return "overdue" if d < today else "today" if d == today else "later"


def _attention_score(t: dict, today: date, pinned_ids: set) -> int:
    """Higher = wants attention sooner. Importance, not chronology."""
    s = 0
    if str(t.get("id")) in pinned_ids:
        s += 100
    st = _due_state(t.get("due_date"), today)
    s += {"overdue": 45, "today": 22, "later": 4, "none": 0}[st]
    if t.get("priority") == "high":
        s += 25
    theme = (t.get("theme") or "").lower()
    if any(k in theme for k in _CASE_WORK):
        s += 8
    return s


def _read_cache(name: str) -> dict:
    try:
        return json.loads((repo_root() / "data" / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def gather(today: date, now: datetime) -> dict:
    """Assemble the situation the brief is written from (attention-ranked)."""
    pins = load_pins()
    pinned = set(pins.get("task", []))
    open_tasks = [t for t in load_tasks() if not t.get("completed")]
    ranked = sorted(open_tasks, key=lambda t: -_attention_score(t, today, pinned))

    # Today's fixed points (timed meetings) from the glance cache.
    tstr = today.isoformat()
    meetings = []
    for evs in _read_cache("glance_cache.json").get("events", {}).values():
        for e in evs:
            if e.get("date") == tstr and e.get("when") and e["when"] != "all day":
                meetings.append((e["when"], e.get("title", "")))
    meetings = sorted(set(meetings))

    # Reminders due today/overdue.
    rem = [r for r in _read_cache("reminders_cache.json").get("items", [])
           if r.get("due") and r["due"][:10] <= tstr]

    # Mail worth attention — the case/work-context items surface first.
    msgs = _read_cache("inbox_cache.json").get("items", [])
    weighted = sorted(
        msgs, key=lambda m: (0 if m.get("context") in ("legal", "work", "consulting") else 1,
                             m.get("date") or ""), reverse=False)
    top_msgs = [m for m in weighted if m.get("context") in ("legal", "work", "consulting")][:4]

    return {
        "now": now, "today": today, "meetings": meetings,
        "overdue": [t for t in ranked if _due_state(t.get("due_date"), today) == "overdue"],
        "due_today": [t for t in ranked if _due_state(t.get("due_date"), today) == "today"],
        "pinned_tasks": [t for t in ranked if str(t.get("id")) in pinned],
        "top_tasks": ranked[:5],
        "reminders": rem,
        "messages": top_msgs,
        "n_open": len(open_tasks),
    }


def _situation_text(g: dict) -> str:
    now = g["now"]
    lines = [f"Now: {now.strftime('%A %-d %B, %H:%M')}."]
    if g["meetings"]:
        lines.append("Fixed points today: "
                     + "; ".join(f"{t} {ti[:34]}" for t, ti in g["meetings"]))
    else:
        lines.append("No meetings scheduled today.")
    if g["pinned_tasks"]:
        lines.append("Pinned (his explicit priorities): "
                     + "; ".join(t["title"] for t in g["pinned_tasks"][:5]))
    if g["overdue"]:
        lines.append("Overdue: " + "; ".join(t["title"] for t in g["overdue"][:5]))
    if g["due_today"]:
        lines.append("Due today: " + "; ".join(t["title"] for t in g["due_today"][:5]))
    if not (g["overdue"] or g["due_today"]) and g["top_tasks"]:
        lines.append("Top open tasks: " + "; ".join(t["title"] for t in g["top_tasks"][:4]))
    if g["reminders"]:
        lines.append("Reminders due: " + "; ".join(r["title"] for r in g["reminders"][:4]))
    if g["messages"]:
        lines.append("Mail worth attention: "
                     + "; ".join(f"[{m['context']}] {m['who']}: {m['subject'][:40]}"
                                 for m in g["messages"]))
    return "\n".join(lines)


_PROMPT = (
    "You are Adam's calm, situational personal assistant (he has ADHD). From his situation "
    "below, write a SHORT orientation that helps him feel on top of things without overwhelm.\n\n"
    "Return ONLY JSON: {\"brief\": \"...\", \"moves\": [\"...\", \"...\"]}.\n"
    "- brief: 2-4 warm, plain sentences. Greet by time of day. Say where he is in the day and "
    "the next fixed point. Then name what MOST deserves attention right now — ranked by "
    "IMPORTANCE, not by what's chronologically soonest. A gentle, energy-aware steer is welcome "
    "(if it's late/quiet, say so). No hype, no lists inside the brief.\n"
    "- moves: 2-3 concrete next actions, MOST IMPORTANT FIRST (not earliest-scheduled first). "
    "Each a short imperative phrase.\n"
    "Base the brief and moves ONLY on the SITUATION below — do not invent tasks, deadlines, or "
    "details that aren't listed. Surface case/work items plainly if they matter, but never give "
    "legal advice, analysis, or clinical labels — you orient, you don't advocate. Invite, don't "
    "command.\n\nSITUATION:\n"
)

# Answer purely from the prompt — no repo exploration (keeps the brief grounded, fast, private).
_NO_TOOLS = ["Bash", "Read", "Edit", "Write", "Glob", "Grep", "WebFetch", "WebSearch"]


def _fallback(g: dict) -> dict:
    """Deterministic brief if claude is unavailable — still narrative, attention-first."""
    h = g["now"].hour
    greet = ("Good morning" if h < 12 else "Good afternoon" if h < 18 else "Good evening")
    parts = [f"{greet}. It's {g['now'].strftime('%A, %H:%M')}."]
    if g["meetings"]:
        nxt = g["meetings"][0]
        parts.append(f"Next fixed point: {nxt[1][:34]} at {nxt[0]}.")
    else:
        parts.append("Nothing fixed in the diary today.")
    if g["pinned_tasks"]:
        parts.append(f"Your pinned focus: {g['pinned_tasks'][0]['title']}.")
    elif g["overdue"]:
        parts.append(f"{len(g['overdue'])} overdue — {g['overdue'][0]['title']} is the one to clear.")
    elif g["due_today"]:
        parts.append(f"{len(g['due_today'])} due today; start with {g['due_today'][0]['title']}.")
    moves = []
    for t in (g["pinned_tasks"] + g["overdue"] + g["due_today"] + g["top_tasks"]):
        if t["title"] not in moves:
            moves.append(t["title"])
        if len(moves) >= 3:
            break
    if g["messages"]:
        moves.insert(0, f"Reply to {g['messages'][0]['who']}")
    return {"brief": " ".join(parts), "moves": moves[:3]}


def refresh(*, now: datetime | None = None, timeout: int = 90) -> dict:
    """Generate the brief (claude, else fallback), cache it, return {brief, moves, at}."""
    now = now or datetime.now()
    g = gather(now.date(), now)
    result = None
    try:
        # Prompt FIRST, then the variadic --disallowedTools at the end (so it can't swallow it).
        out = subprocess.run(
            ["claude", "-p", _PROMPT + _situation_text(g), "--disallowedTools", *_NO_TOOLS],
            capture_output=True, text=True, timeout=timeout, check=False)
        if out.returncode == 0 and out.stdout.strip():
            txt = out.stdout.strip()
            i, j = txt.find("{"), txt.rfind("}")
            if i != -1 and j != -1:
                parsed = json.loads(txt[i:j + 1])
                if parsed.get("brief"):
                    result = {"brief": str(parsed["brief"]),
                              "moves": [str(m) for m in (parsed.get("moves") or [])][:3]}
    except (subprocess.SubprocessError, OSError, ValueError):
        result = None
    if result is None:
        result = _fallback(g)
    result["at"] = now.isoformat(timespec="minutes")
    p = _cache()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    d = refresh()
    print(d["brief"])
    for m in d["moves"]:
        print("  →", m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
