#!/usr/bin/env python3
"""smoke.py — one command to test the whole PA end-to-end, safely.

Run:  python3 tests/smoke.py

Exercises every deterministic component and safe read path, printing PASS/FAIL per check
and a summary (exit 0 if all pass, 1 otherwise). SAFE BY DESIGN:
  - task writes go to a TEMP store, never data/tasks.json
  - live sources (gog/himalaya/OneDrive) are read-only; empty results are tolerated
  - NOTHING is sent (no Signal, no mail); scripts are syntax-checked, not fired
  - Apple Notes / real store are not written

For the phone/Signal/visual bits a script can't judge, see TESTING.md.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

CHECKS: list[tuple[str, callable]] = []


def check(name: str):
    """Register a check; a check passes if it returns without raising."""
    def deco(fn):
        CHECKS.append((name, fn))
        return fn
    return deco


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, timeout=60, **kw)


# --- task store + schema (temp store, no real-data writes) --------------------

@check("taskstore: add/load/render carries energy+theme+priority+steps")
def _t_store():
    from lib.taskstore import add_task, load_tasks, render_markdown
    with tempfile.TemporaryDirectory() as d:
        store = Path(d) / "t.json"
        t = add_task("Smoke task", category="Work", theme="Enact", priority="high",
                     energy="low", estimate_min=15, steps=["open file", "write line"],
                     json_path=store, md_path=store.with_suffix(".md"))
        assert t["theme"] == "Enact" and t["priority"] == "high", t
        assert t["energy"] == "low" and t["estimate_min"] == 15 and len(t["steps"]) == 2, t
        tasks = load_tasks(store)
        assert len(tasks) == 1, tasks
        md = render_markdown(tasks)
        assert "Smoke task" in md and "low" in md, md


@check("taskstore: complete_task marks done + records completed_at")
def _t_complete():
    from lib.taskstore import add_task, complete_task, load_tasks
    with tempfile.TemporaryDirectory() as d:
        store = Path(d) / "t.json"
        md = store.with_suffix(".md")
        t = add_task("finish me", json_path=store, md_path=md)
        done = complete_task(t["id"], json_path=store, md_path=md)
        assert done and done["completed"] is True and done.get("completed_at"), done
        assert load_tasks(store)[0]["completed"] is True


@check("capture CLI: writes task with new fields to a temp store")
def _t_capture():
    with tempfile.TemporaryDirectory() as d:
        store = Path(d) / "c.json"
        r = run(["python3", "skills/task-capture/capture.py", "CLI smoke",
                 "--theme", "ZigZag", "--priority", "normal", "--energy", "medium",
                 "--estimate", "20", "--step", "first step",
                 "--store", str(store), "--no-notes"])
        assert r.returncode == 0, r.stderr
        obj = json.loads(r.stdout)
        assert obj["theme"] == "ZigZag" and obj["estimate_min"] == 20, obj
        assert obj["steps"] == ["first step"], obj


# --- focus (integration, real store, read-only) -------------------------------

@check("focus: theme view runs and lists tasks")
def _t_focus_theme():
    r = run(["python3", "skills/focus/focus.py", "ZigZag"])
    assert r.returncode == 0, r.stderr
    assert "# Focus" in r.stdout and "Tasks (" in r.stdout, r.stdout


@check("focus: --energy quick-wins filter runs")
def _t_focus_energy():
    r = run(["python3", "skills/focus/focus.py", "--energy", "low"])
    assert r.returncode == 0, r.stderr
    assert "Focus" in r.stdout, r.stdout


# --- unified activity + dashboard (read-only live + gitignored html) ----------

@check("activity: unified() returns a sorted list")
def _t_activity():
    from lib.activity import unified
    items = unified(days=14)
    assert isinstance(items, list), type(items)
    # soonest-first: dated items should be non-decreasing by timestamp
    dated = [a.timestamp for a in items if a.timestamp]
    assert dated == sorted(dated), "activity stream is not soonest-first"


@check("dashboard: builds and contains all sections")
def _t_dashboard():
    r = run(["python3", "build_pa_dashboard.py"])
    assert r.returncode == 0, r.stderr
    htmlfile = REPO / "data" / "PA_DASHBOARD.html"
    body = htmlfile.read_text(encoding="utf-8")
    for h in ("Upcoming", "Needs a look", "Tasks", "Recent activity"):
        assert h in body, f"missing section: {h}"


# --- extracted assets ---------------------------------------------------------

@check("extracted: all JSON banks parse")
def _t_extracted():
    for name in ("prompt_bank.json", "action_learning_questions.json",
                 "taxonomy.json", "reflection_prompts.json"):
        json.loads((REPO / "extracted" / name).read_text(encoding="utf-8"))


# --- read-only source plumbing (tolerant of empty/offline) --------------------

@check("comms: calendar + inbox helpers run without error")
def _t_comms():
    from lib.comms import ACCOUNTS, calendar_events, fetch_inbox
    from datetime import date
    acct = ACCOUNTS[0]
    assert isinstance(calendar_events(acct["cal"], date.today(), date.today()), list)
    assert isinstance(fetch_inbox(acct["mail"], limit=3), list)


@check("onedrive: render returns a string")
def _t_onedrive():
    from lib.onedrive import render
    assert isinstance(render(days=7), str)


# --- shell scripts: syntax only (never fire a send) ---------------------------

@check("scripts: run_checkin.sh + nudge.sh are syntactically valid")
def _t_scripts():
    for s in ("schedule/run_checkin.sh", "schedule/nudge.sh"):
        r = run(["bash", "-n", s])
        assert r.returncode == 0, f"{s}: {r.stderr}"


# --- monitor + state (dry, temp state, no sends) ------------------------------

@check("state: save/load roundtrip + dedup ledger")
def _t_state():
    from datetime import datetime
    from lib.state import already_nudged, load_state, record_nudge, save_state
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "state.json"
        s = load_state(p)
        assert s["seeded"] is False
        record_nudge(s, "evt:1", datetime(2026, 7, 21, 9, 0, 0))
        save_state(s, p)
        assert already_nudged(load_state(p), "evt:1")


@check("monitor: seeds first pass, no-ops second (dry, temp state)")
def _t_monitor():
    with tempfile.TemporaryDirectory() as d:
        st = Path(d) / "state.json"
        r1 = run(["python3", "skills/monitor/monitor.py", "--once", "--dry", "--state", str(st)])
        assert r1.returncode == 0 and "seeded" in r1.stdout, r1.stdout + r1.stderr
        r2 = run(["python3", "skills/monitor/monitor.py", "--once", "--dry", "--state", str(st)])
        assert r2.returncode == 0 and "events=" in r2.stdout, r2.stdout + r2.stderr


def main() -> int:
    passed, failed = 0, 0
    print("PA smoke test\n" + "=" * 40)
    for name, fn in CHECKS:
        try:
            fn()
            print(f"  ✓ {name}")
            passed += 1
        except Exception as exc:  # noqa: BLE001 — a smoke runner reports, never crashes
            print(f"  ✗ {name}\n      {type(exc).__name__}: {exc}")
            failed += 1
    print("=" * 40)
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
