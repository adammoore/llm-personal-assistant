#!/usr/bin/env python3
"""task-capture — append a task to the local task store with minimal friction.

Thin CLI over lib/taskstore.py (which owns the JSON store + markdown mirror). The skill
(Claude) extracts a clean title, optional category/due date from free text, then calls this.

Usage:
    capture.py "Call the dentist" --category Health --due 2026-07-25 --source signal
    capture.py "Email Beverley re FDR"        # category defaults to Other

Exit codes: 0 ok (prints the created record as JSON), 2 on bad input.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make the repo-root importable so `lib` resolves regardless of the cwd the skill runs from.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lib.applenotes import append_to_pa_note  # noqa: E402
from lib.taskstore import CATEGORIES, DEFAULT_CATEGORY, add_task  # noqa: E402


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Capture a task into the local store.")
    p.add_argument("title", help="the task, in plain words")
    p.add_argument("--category", default=DEFAULT_CATEGORY, choices=CATEGORIES)
    p.add_argument("--due", default=None, help="due date, ISO YYYY-MM-DD")
    p.add_argument("--description", default=None, help="optional extra detail")
    p.add_argument("--source", default="chat", help="where the task came from (chat/signal)")
    p.add_argument("--store", default=None, type=Path,
                   help="override JSON store path (testing); .md mirror sits beside it")
    p.add_argument("--no-notes", action="store_true",
                   help="do not mirror the task into the Apple Notes 'PA Inbox' note")
    return p.parse_args(argv)


def _notes_line(task: dict) -> str:
    """One-line rendering of a task for the PA Inbox note."""
    line = f"☐ {task['title']} [{task['category']}]"
    if task.get("due_date"):
        line += f" — due {task['due_date']}"
    return line


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    md_path = args.store.with_suffix(".md") if args.store else None
    task = add_task(
        args.title,
        category=args.category,
        due=args.due,
        description=args.description,
        source=args.source,
        json_path=args.store,
        md_path=md_path,
    )
    # Mirror into the dedicated Apple Notes "PA Inbox" (best-effort; the local store is
    # canonical, so a Notes/permission failure must not fail the capture).
    task["mirrored_to_notes"] = False
    if not args.no_notes and args.store is None:
        task["mirrored_to_notes"] = append_to_pa_note(_notes_line(task))
    print(json.dumps(task, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
