#!/usr/bin/env python3
"""quick_win — suggest the lowest-activation task to start with.

Energy-aware nudging without asking Adam his energy: on a flat morning the hardest part is
starting, so surface the *easiest* real entry point — lowest energy, shortest, ideally with
a first step already written. Prints ONE short line (or nothing, if the store is empty) that
the daily check-in appends to its Signal invitation.

Usage:  python3 skills/checkin-daily/quick_win.py   ->  "Easiest start: X ▸ first step"
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lib.taskstore import load_tasks, priority_rank  # noqa: E402

_ENERGY_RANK = {"low": 0, "medium": 1, "high": 2}


def _rank(task: dict) -> tuple:
    """Lower is easier to start: least energy, shortest, has-a-step, then priority."""
    energy = _ENERGY_RANK.get(task.get("energy", "medium"), 1)
    estimate = task.get("estimate_min") or 9999
    has_step = 0 if (task.get("steps") or []) else 1
    return (energy, estimate, has_step, priority_rank(task))


def pick(tasks: list[dict]) -> dict | None:
    """The single lowest-activation open task, or None if there are none."""
    open_tasks = [t for t in tasks if not t.get("completed")]
    return min(open_tasks, key=_rank) if open_tasks else None


def suggestion_line(task: dict | None) -> str:
    """One gentle line naming the easiest start (empty string if nothing to suggest)."""
    if not task:
        return ""
    line = f"Easiest start: {task['title']}"
    steps = task.get("steps") or []
    if steps:
        line += f" ▸ {steps[0]}"
    return line


def main() -> int:
    line = suggestion_line(pick(load_tasks()))
    if line:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
