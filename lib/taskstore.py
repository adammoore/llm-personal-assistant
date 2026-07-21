#!/usr/bin/env python3
"""taskstore — the one module that owns the local task store.

Shared by every skill that touches tasks (`task-capture` writes; `checkin-*` and
`build_pa_dashboard.py` read). Keeping load/save/render here means the JSON store and its
human-readable markdown mirror can never drift apart: `save_tasks()` rewrites both.

Store (ADR-001 §2, git-ignored/private):
  - data/tasks.json  — canonical JSON array (machines read/write this)
  - data/tasks.md    — auto-generated human mirror (never hand-edit)

Each task: {id, title, description, category, theme, priority, due_date, completed,
created_at, source, energy, estimate_min, steps}
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Category taxonomy carried forward from the legacy app (extracted/taxonomy.json).
CATEGORIES = ["Work", "Personal", "Health", "Finance", "Other"]
DEFAULT_CATEGORY = "Other"

# Priority for focus/sorting; theme is a free project tag (e.g. "Enact", "Case", "House").
PRIORITIES = ["high", "normal", "low"]
DEFAULT_PRIORITY = "normal"
_PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}

# Energy = how much fuel a task demands, not how urgent it is. Kept separate from priority
# so a low-energy quick win can be surfaced on a flat day without touching what matters most
# (salvaged from Adam's earlier ADHD PAs — "match the task to the tank, not the guilt").
ENERGIES = ["low", "medium", "high"]
DEFAULT_ENERGY = "medium"


def repo_root() -> Path:
    """Repo root is one level up from this file (lib/taskstore.py)."""
    return Path(__file__).resolve().parents[1]


def json_store() -> Path:
    """Canonical JSON store path."""
    return repo_root() / "data" / "tasks.json"


def md_store() -> Path:
    """Human-readable markdown mirror path."""
    return repo_root() / "data" / "tasks.md"


def load_tasks(store: Path | None = None) -> list[dict]:
    """Return the task list, or [] if the store does not exist yet.

    Raises SystemExit(2) rather than overwrite a store we cannot parse.
    """
    store = store or json_store()
    if not store.exists():
        return []
    try:
        data = json.loads(store.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: {store} is not valid JSON ({exc}); refusing to overwrite",
              file=sys.stderr)
        raise SystemExit(2) from exc
    if not isinstance(data, list):
        print(f"error: {store} does not contain a JSON array", file=sys.stderr)
        raise SystemExit(2)
    return data


def next_id(tasks: list[dict]) -> int:
    """Monotonic id: one past the current max (ids are never reused)."""
    return max((int(t.get("id", 0)) for t in tasks), default=0) + 1


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file + replace so a crash can't truncate the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def save_tasks(tasks: list[dict], *, json_path: Path | None = None,
               md_path: Path | None = None, now: datetime | None = None) -> None:
    """Persist the JSON store AND regenerate the markdown mirror atomically."""
    json_path = json_path or json_store()
    md_path = md_path or md_store()
    _atomic_write(json_path, json.dumps(tasks, indent=2, ensure_ascii=False) + "\n")
    _atomic_write(md_path, render_markdown(tasks, now=now))


def add_task(
    title: str,
    *,
    category: str = DEFAULT_CATEGORY,
    due: str | None = None,
    description: str | None = None,
    source: str = "chat",
    theme: str | None = None,
    priority: str = DEFAULT_PRIORITY,
    energy: str = DEFAULT_ENERGY,
    estimate_min: int | None = None,
    steps: list[str] | None = None,
    json_path: Path | None = None,
    md_path: Path | None = None,
    now: datetime | None = None,
) -> dict:
    """Append one task, persist both stores, and return the created record."""
    title = title.strip()
    if not title:
        print("error: empty task title", file=sys.stderr)
        raise SystemExit(2)
    if category not in CATEGORIES:
        print(f"error: category must be one of {CATEGORIES}", file=sys.stderr)
        raise SystemExit(2)
    if priority not in PRIORITIES:
        print(f"error: priority must be one of {PRIORITIES}", file=sys.stderr)
        raise SystemExit(2)
    if energy not in ENERGIES:
        print(f"error: energy must be one of {ENERGIES}", file=sys.stderr)
        raise SystemExit(2)

    tasks = load_tasks(json_path)
    created_at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    # Keep the original field order intact; the ENERGY/BREAKDOWN dimensions append at the end.
    task = {
        "id": next_id(tasks),
        "title": title,
        "description": description or None,
        "category": category,
        "theme": (theme or None),
        "priority": priority,
        "due_date": due,
        "completed": False,
        "created_at": created_at,
        "source": source,
        "energy": energy,
        "estimate_min": estimate_min,
        # First concrete steps, kept short to lower activation energy (nothing to plan, just start).
        "steps": [s.strip() for s in (steps or []) if s.strip()],
    }
    tasks.append(task)
    save_tasks(tasks, json_path=json_path, md_path=md_path, now=now)
    return task


def complete_task(task_id: int, *, json_path: Path | None = None,
                  md_path: Path | None = None, now: datetime | None = None) -> dict | None:
    """Mark a task complete (records completed_at) and persist. Returns it, or None if absent."""
    tasks = load_tasks(json_path)
    for t in tasks:
        if int(t.get("id", -1)) == int(task_id):
            t["completed"] = True
            t["completed_at"] = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
            save_tasks(tasks, json_path=json_path, md_path=md_path, now=now)
            return t
    return None


_EDITABLE = {"title", "category", "theme", "priority", "energy", "due_date", "description"}


def update_task(task_id: int, fields: dict, *, json_path: Path | None = None,
                md_path: Path | None = None, now: datetime | None = None) -> dict | None:
    """Edit a task's fields (title/category/theme/priority/energy/due_date/description).

    Only whitelisted keys apply. For theme/due_date/description an empty value clears the
    field; an empty title is ignored. Invalid category/priority/energy are dropped. Returns
    the updated task, or None if not found.
    """
    tasks = load_tasks(json_path)
    for t in tasks:
        if int(t.get("id", -1)) != int(task_id):
            continue
        for k, v in fields.items():
            if k not in _EDITABLE:
                continue
            v = v.strip() if isinstance(v, str) else v
            if k == "title":
                if v:
                    t[k] = v
            elif k == "category" and v not in CATEGORIES:
                continue
            elif k == "priority" and v not in PRIORITIES:
                continue
            elif k == "energy" and v not in ENERGIES:
                continue
            elif k in ("theme", "due_date", "description"):
                t[k] = v or None
            else:
                t[k] = v
        save_tasks(tasks, json_path=json_path, md_path=md_path, now=now)
        return t
    return None


def set_steps(task_id: int, steps: list[str], *, json_path: Path | None = None,
              md_path: Path | None = None, now: datetime | None = None) -> dict | None:
    """Replace a task's breakdown steps (Magic ToDo) and persist. Returns it, or None."""
    tasks = load_tasks(json_path)
    for t in tasks:
        if int(t.get("id", -1)) == int(task_id):
            t["steps"] = [s.strip() for s in steps if s and s.strip()]
            save_tasks(tasks, json_path=json_path, md_path=md_path, now=now)
            return t
    return None


def render_markdown(tasks: list[dict], *, now: datetime | None = None) -> str:
    """Render the store as a grouped, human-readable markdown document."""
    stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    lines = [
        "# Tasks",
        "",
        f"_Auto-generated from `tasks.json` at {stamp} — do not edit by hand._",
        "",
    ]

    open_tasks = [t for t in tasks if not t.get("completed")]
    done_tasks = [t for t in tasks if t.get("completed")]

    lines.append(f"## Open ({len(open_tasks)})")
    lines.append("")
    if not open_tasks:
        lines.append("_Nothing open — a clear slate._")
        lines.append("")
    else:
        # Group by the fixed category order so the document is stable.
        for category in CATEGORIES:
            group = [t for t in open_tasks if t.get("category") == category]
            if not group:
                continue
            lines.append(f"### {category}")
            for t in sorted(group, key=lambda x: (x.get("due_date") or "9999", x["id"])):
                lines.append(_task_line(t))
            lines.append("")

    if done_tasks:
        lines.append(f"## Done ({len(done_tasks)})")
        lines.append("")
        for t in sorted(done_tasks, key=lambda x: x["id"]):
            lines.append(_task_line(t))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _task_line(t: dict) -> str:
    """One markdown checklist line for a task."""
    box = "x" if t.get("completed") else " "
    flag = "‼ " if t.get("priority") == "high" else ""
    parts = [f"- [{box}] {flag}#{t['id']} {t['title']}"]
    if t.get("theme"):
        parts.append(f"#{t['theme']}")
    # Energy is always present (defaulted); estimate and steps only show when set — a
    # compact "·low (10 min) ▸ 2 steps" so the tank/effort read is glanceable, not noisy.
    parts.append(f"·{t.get('energy', DEFAULT_ENERGY)}")
    if t.get("estimate_min"):
        parts.append(f"({t['estimate_min']} min)")
    if t.get("steps"):
        parts.append(f"▸ {len(t['steps'])} steps")
    if t.get("due_date"):
        parts.append(f"— due {t['due_date']}")
    if t.get("description"):
        parts.append(f"— {t['description']}")
    suffix = f"  · _{t.get('source', 'chat')}_"
    return " ".join(parts) + suffix


def priority_rank(task: dict) -> int:
    """Sort key: high→0, normal→1, low→2 (unknown treated as normal)."""
    return _PRIORITY_RANK.get(task.get("priority", DEFAULT_PRIORITY), 1)
