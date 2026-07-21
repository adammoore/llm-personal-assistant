#!/usr/bin/env python3
"""magictodo — break a task into concrete steps (goblin.tools Magic ToDo style).

The LLM is Claude itself: this shells out to `claude -p` (Adam's Claude Code runtime, no API
key) and parses the steps. Spiciness = granularity, 1 (few big steps) → 5 (many tiny ones).

Read-only w.r.t. the world; the caller saves the steps onto the task.
"""

from __future__ import annotations

import re
import subprocess

_STEPS_FOR = {1: 3, 2: 4, 3: 5, 4: 7, 5: 10}
_PREFIX = re.compile(r"^\s*(?:\d+[.)]|[-*••])\s*")


def breakdown(title: str, spiciness: int = 3, *, timeout: int = 90) -> list[str]:
    """Return concrete steps for a task title, or [] on any failure."""
    title = (title or "").strip()
    if not title:
        return []
    n = _STEPS_FOR.get(int(spiciness), 5)
    prompt = (
        f"Break this task into {n} concrete, actionable steps in the spirit of goblin.tools "
        f"Magic ToDo (spiciness {spiciness}/5 = how granular; higher = smaller steps). "
        f"Output ONLY the steps, one per line — no numbering, no bullets, no preamble, no "
        f"commentary. Task: {title}"
    )
    try:
        out = subprocess.run(["claude", "-p", prompt],
                             capture_output=True, text=True, timeout=timeout)
    except (subprocess.SubprocessError, OSError):
        return []
    if out.returncode != 0:
        return []
    steps = []
    for line in out.stdout.splitlines():
        s = _PREFIX.sub("", line).strip()
        if s:
            steps.append(s)
    return steps[:12]
