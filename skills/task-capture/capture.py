#!/usr/bin/env python3
"""task-capture — append a task to the local task store with minimal friction.

Deterministic helper behind the `task-capture` skill (ADR-001 §2). The skill (Claude)
extracts a clean title, optional category/due date from free text, then calls this script,
which owns the store format so writes stay consistent and idempotent-ish.

Store: JSON array at <repo>/data/tasks.json (git-ignored, private). Each task:
    {id, title, description, category, due_date, completed, created_at, source}

Usage:
    capture.py "Call the dentist" --category Health --due 2026-07-25 --source signal
    capture.py "Email Beverley re FDR"        # category defaults to Other

Exit codes: 0 ok (prints the created record as JSON), 2 on bad input.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Category taxonomy carried forward from the legacy app (extracted/taxonomy.json).
CATEGORIES = ["Work", "Personal", "Health", "Finance", "Other"]
DEFAULT_CATEGORY = "Other"


def repo_root() -> Path:
    """Repo root is two levels up from this file (skills/task-capture/capture.py)."""
    return Path(__file__).resolve().parents[2]


def default_store() -> Path:
    """Canonical task store path; created on first write."""
    return repo_root() / "data" / "tasks.json"


def load_tasks(store: Path) -> list[dict]:
    """Return the task list, or [] if the store does not exist yet."""
    if not store.exists():
        return []
    try:
        data = json.loads(store.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # never clobber a corrupt store silently
        print(f"error: {store} is not valid JSON ({exc}); refusing to overwrite",
              file=sys.stderr)
        raise SystemExit(2) from exc
    if not isinstance(data, list):
        print(f"error: {store} does not contain a JSON array", file=sys.stderr)
        raise SystemExit(2)
    return data


def next_id(tasks: list[dict]) -> int:
    """Monotonic id: one past the current max (ids never reused)."""
    return max((int(t.get("id", 0)) for t in tasks), default=0) + 1


def add_task(
    title: str,
    *,
    category: str = DEFAULT_CATEGORY,
    due: str | None = None,
    description: str | None = None,
    source: str = "chat",
    store: Path | None = None,
    now: datetime | None = None,
) -> dict:
    """Append one task to the store and return the created record."""
    title = title.strip()
    if not title:
        print("error: empty task title", file=sys.stderr)
        raise SystemExit(2)
    if category not in CATEGORIES:
        print(f"error: category must be one of {CATEGORIES}", file=sys.stderr)
        raise SystemExit(2)

    store = store or default_store()
    tasks = load_tasks(store)
    created_at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    task = {
        "id": next_id(tasks),
        "title": title,
        "description": description or None,
        "category": category,
        "due_date": due,
        "completed": False,
        "created_at": created_at,
        "source": source,
    }
    tasks.append(task)
    store.parent.mkdir(parents=True, exist_ok=True)
    # Write atomically-ish: temp file then replace, so a crash can't truncate the store.
    tmp = store.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(tasks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(store)
    return task


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Capture a task into the local store.")
    p.add_argument("title", help="the task, in plain words")
    p.add_argument("--category", default=DEFAULT_CATEGORY, choices=CATEGORIES)
    p.add_argument("--due", default=None, help="due date, ISO YYYY-MM-DD")
    p.add_argument("--description", default=None, help="optional extra detail")
    p.add_argument("--source", default="chat", help="where the task came from (chat/signal)")
    p.add_argument("--store", default=None, type=Path, help="override store path (testing)")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    task = add_task(
        args.title,
        category=args.category,
        due=args.due,
        description=args.description,
        source=args.source,
        store=args.store,
    )
    print(json.dumps(task, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
