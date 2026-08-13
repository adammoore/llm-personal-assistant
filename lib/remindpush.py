#!/usr/bin/env python3
"""remindpush — surface PA tasks on Apple Reminders (an OFF-DESKTOP surface).

The dashboard is a desktop surface; this pushes the open task list into a dedicated 'PA Tasks'
Reminders list via `remindctl`, so tasks ride to iPhone/Watch and Siri can read or complete them.

One-way, PA-is-source-of-truth: new open tasks are added; when a task is completed or deleted in
the PA, its reminder is completed. Each reminder carries url `pa-task:<id>` for provenance, and a
local map (data/pushed_reminders.json) tracks task_id → reminder id so re-runs never duplicate and
only ever touch PA-created reminders (never Adam's own).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from lib.taskstore import complete_task, load_tasks, repo_root

LIST = "PA Tasks"
STATE = repo_root() / "data" / "pushed_reminders.json"


def available() -> bool:
    return shutil.which("remindctl") is not None


def _ensure_list() -> None:
    """Create the 'PA Tasks' list if absent (remindctl can't create lists; AppleScript can)."""
    script = ('tell application "Reminders"\n'
              f' if not (exists list "{LIST}") then make new list with properties {{name:"{LIST}"}}\n'
              'end tell')
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
    except (subprocess.SubprocessError, OSError):
        pass


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(m: dict) -> None:
    try:
        STATE.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def _add(t: dict) -> str | None:
    cmd = ["remindctl", "add", t.get("title") or "(task)", "-l", LIST,
           "--url", f"pa-task:{t['id']}", "--json", "--no-input"]
    if t.get("due_date"):
        cmd += ["-d", t["due_date"]]
    prio = {"high": "high", "low": "low"}.get(t.get("priority"))
    if prio:
        cmd += ["-p", prio]
    note = " · ".join(b for b in (t.get("theme"), t.get("category")) if b)
    if note:
        cmd += ["-n", f"{note} (from PA)"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (json.loads(out.stdout or "{}") or {}).get("id")
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def _complete(rid: str) -> None:
    try:
        subprocess.run(["remindctl", "complete", rid, "--no-input"], capture_output=True, timeout=15)
    except (subprocess.SubprocessError, OSError):
        pass


def _completed_pa_reminders() -> list[dict]:
    """Reminders ticked off (on phone/Watch/Siri) in the 'PA Tasks' list — for the return trip."""
    try:
        out = subprocess.run(["remindctl", "show", "completed", "-l", LIST, "--json", "--no-input"],
                             capture_output=True, text=True, timeout=20)
        data = json.loads(out.stdout or "[]")
        return data if isinstance(data, list) else data.get("reminders", [])
    except (subprocess.SubprocessError, OSError, ValueError):
        return []


def sync() -> dict:
    """Reconcile the PA's open tasks into the 'PA Tasks' Reminders list. Returns a small report."""
    if not available():
        return {"ok": False, "error": "remindctl not installed"}
    _ensure_list()
    pushed = _load()                                       # {task_id: reminder_id}
    tasks = load_tasks()
    by_id = {str(t["id"]): t for t in tasks}
    added, completed, pulled = [], 0, []

    # PULL (return trip): a 'PA Tasks' reminder ticked off on the phone/Watch → complete the PA task.
    for r in _completed_pa_reminders():
        url = r.get("url") or ""
        tid = url.split("pa-task:", 1)[1] if "pa-task:" in url else None
        if tid and tid in pushed:
            t = by_id.get(tid)
            if t and not t.get("completed"):
                try:
                    complete_task(int(tid))
                    pulled.append(t.get("title") or tid)
                except (ValueError, TypeError):
                    pass
            del pushed[tid]

    # PUSH: open tasks not yet on the list → add.
    for t in tasks:
        tid = str(t["id"])
        if t.get("completed") or tid in pushed:
            continue
        rid = _add(t)
        if rid:
            pushed[tid] = rid
            added.append(t.get("title") or tid)

    # RECONCILE: a PA task completed/deleted here → complete its reminder.
    for tid, rid in list(pushed.items()):
        t = by_id.get(tid)
        if t is None or t.get("completed"):
            _complete(rid)
            del pushed[tid]
            completed += 1

    _save(pushed)
    return {"ok": True, "added": added, "pulled": pulled, "completed": completed, "live": len(pushed)}


def main() -> int:
    r = sync()
    if not r.get("ok"):
        print("remindpush:", r.get("error"))
        return 1
    print(f"PA Tasks → Reminders: +{len(r['added'])} added, {r['completed']} completed, "
          f"{r['live']} live")
    for a in r["added"]:
        print("  +", a)
    return 0


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
