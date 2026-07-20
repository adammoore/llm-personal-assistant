#!/usr/bin/env python3
"""quarterly-review assemble — gather the DETERMINISTIC raw material for a quarter.

The read-only data-gathering half of the `quarterly-review` skill (ADR-001 §goal 5).
It collects only the *local, deterministic* sources — no MCP, no network — so the skill
can then enrich them with Granola meetings and the evidence store at runtime and
synthesise a draft. Everything here is at the **autonomous** tier: it reads and
summarises (daily/weekly/monthly notes, the local task store, git history) and writes a
single digest file. It never sends, drafts, or mutates anything Adam relies on.

The output is deliberately framed as *raw material*, not a verdict: wins surfaced first,
nothing itemised as debt. The skill turns this into a draft; a human turns the draft into
the review.

Output: a structured markdown digest to stdout AND written to
data/reviews/<quarter>.md (e.g. 2026-Q3.md), created if missing.

Usage: python3 skills/quarterly-review/assemble.py [--from YYYY-MM-DD] [--to YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lib.taskstore import CATEGORIES, load_tasks, repo_root  # noqa: E402

# Where the period notes live (ADR-001 target layout). Missing dirs are fine — skipped.
NOTE_DIRS = {"daily": "data/daily", "weekly": "data/weekly", "monthly": "data/monthly"}

# Section headings we lift verbatim from a note (case-insensitive substring match).
# These are the human-authored parts worth carrying into a review; everything else in a
# note is auto-generated glance content and stays out of the digest.
LIFT_SECTIONS = ("intention", "reflection", "what changed", "win")

# A line that is *only* an italic placeholder, e.g. "_(optional)_" — skip these so empty
# note stubs don't pad the digest with noise.
PLACEHOLDER = re.compile(r"^_.*_$")


def _run(cmd: list[str], timeout: int = 25) -> str:
    """Run a command, returning stdout ('' on any failure — reads must never crash).

    Same defensive pattern as lib.comms._run: a git hiccup degrades the digest, never
    crashes the assemble step.
    """
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.stdout if out.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def quarter_bounds(day: date) -> tuple[date, date, str]:
    """Return (start, end, label) for the calendar quarter containing `day`.

    Labels are the conventional `YYYY-Q<n>` (e.g. 2026-Q3 covers Jul-Sep).
    """
    q = (day.month - 1) // 3  # 0..3
    start_month = q * 3 + 1
    start = date(day.year, start_month, 1)
    # End is the last day of the quarter's final month: the day before the next quarter.
    if start_month + 3 > 12:
        end = date(day.year, 12, 31)
    else:
        end = _prev_day(date(day.year, start_month + 3, 1))
    return start, end, f"{day.year}-Q{q + 1}"


def _prev_day(d: date) -> date:
    """The calendar day before `d` (avoids importing timedelta for one use)."""
    from datetime import timedelta

    return d - timedelta(days=1)


def note_date(stem: str) -> date | None:
    """Best-effort date for a note filename stem.

    Handles the shapes the check-in skills emit and reasonable neighbours:
      - `2026-07-19`      -> that day (daily notes)
      - `2026-07`         -> first of the month (monthly notes)
      - `2026-W29` / `2026-w29` -> Monday of that ISO week (weekly notes)
    Returns None if nothing parses (the file is then skipped, never guessed).
    """
    stem = stem.strip()
    # Full ISO date.
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", stem)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    # ISO week (YYYY-Www) -> Monday of that week.
    m = re.fullmatch(r"(\d{4})-[Ww](\d{1,2})", stem)
    if m:
        try:
            return date.fromisocalendar(int(m[1]), int(m[2]), 1)
        except ValueError:
            return None
    # Year-month -> first of month.
    m = re.fullmatch(r"(\d{4})-(\d{2})", stem)
    if m:
        try:
            return date(int(m[1]), int(m[2]), 1)
        except ValueError:
            return None
    return None


def lift_note(text: str) -> dict[str, list[str]]:
    """Pull the human-authored sections (intentions/reflection/…) out of a note.

    Returns {section_title: [content lines]}, skipping italic placeholder stubs and
    empty sections. Section membership is by markdown heading; content is the non-blank,
    non-placeholder lines beneath each lifted heading until the next heading.
    """
    lifted: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            # Start capturing only under headings we care about.
            current = title if any(k in title.lower() for k in LIFT_SECTIONS) else None
            if current is not None:
                lifted.setdefault(current, [])
            continue
        if current is None:
            continue
        body = line.strip()
        if not body or PLACEHOLDER.match(body):
            continue  # skip blanks and "_(optional)_"-style stubs
        lifted[current].append(body)
    # Drop sections that turned out empty once placeholders were stripped.
    return {k: v for k, v in lifted.items() if v}


def gather_notes(start: date, end: date) -> dict[str, list[dict]]:
    """Collect in-range notes per cadence, newest first, with their lifted sections.

    Returns {cadence: [{date, title, sections}]} for cadences that have any content.
    """
    root = repo_root()
    out: dict[str, list[dict]] = {}
    for cadence, rel in NOTE_DIRS.items():
        directory = root / rel
        if not directory.is_dir():
            continue
        entries: list[dict] = []
        for path in sorted(directory.glob("*.md")):
            when = note_date(path.stem)
            if when is None or not (start <= when <= end):
                continue
            text = path.read_text(encoding="utf-8")
            # First H1 is the note's own title (falls back to the stem).
            title = path.stem
            for line in text.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            entries.append({"date": when, "title": title, "sections": lift_note(text)})
        if entries:
            entries.sort(key=lambda e: e["date"], reverse=True)
            out[cadence] = entries
    return out


def gather_tasks(start: date, end: date) -> dict[str, object]:
    """Summarise task activity for the range from the local store.

    - `created`: tasks whose `created_at` (ISO) falls in range, grouped by category.
    - `wins`: completed tasks (the store carries `completed` as a bool with no completion
      timestamp, so wins are surfaced as-is rather than date-filtered — noted honestly in
      the digest so nothing is over-claimed for the quarter).
    """
    created: dict[str, list[dict]] = {c: [] for c in CATEGORIES}
    wins: list[dict] = []
    lo, hi = start.isoformat(), end.isoformat()
    for t in load_tasks():
        if t.get("completed"):
            wins.append(t)
        created_at = (t.get("created_at") or "")[:10]
        if created_at and lo <= created_at <= hi:
            created.setdefault(t.get("category", "Other"), []).append(t)
    # Drop empty category buckets for a tidy digest.
    created = {c: ts for c, ts in created.items() if ts}
    return {"created": created, "wins": wins}


def gather_git(start: date, end: date) -> dict[str, object]:
    """Summarise git commit activity in range (read-only `git log`).

    Returns {count, notable} where `notable` favours feature/fix commits, falling back to
    the most recent messages. Empty/degraded on any git failure (never crashes).
    """
    root = repo_root()
    # --until is exclusive of the following day's start; add a day's slack via the date
    # itself is fine here because git treats bare dates as local midnight — using the end
    # date as an inclusive-enough bound for a quarter-scale summary.
    raw = _run([
        "git", "-C", str(root), "log",
        f"--since={start.isoformat()}", f"--until={end.isoformat()} 23:59:59",
        "--pretty=format:%h\x1f%ad\x1f%s", "--date=short",
    ])
    if not raw:
        return {"count": 0, "notable": []}
    commits: list[dict] = []
    for line in raw.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 3:
            commits.append({"hash": parts[0], "date": parts[1], "subject": parts[2]})
    # Notable = conventional feat/fix commits; fall back to the newest handful.
    notable = [c for c in commits if re.match(r"(feat|fix)\b", c["subject"], re.IGNORECASE)]
    if not notable:
        notable = commits[:8]
    return {"count": len(commits), "notable": notable[:12]}


def build_digest(start: date, end: date, label: str) -> str:
    """Assemble the deterministic raw-material digest as markdown."""
    notes = gather_notes(start, end)
    tasks = gather_tasks(start, end)
    git = gather_git(start, end)

    span = f"{start.strftime('%-d %b %Y')} – {end.strftime('%-d %b %Y')}"
    lines = [
        f"# Quarterly review — raw material — {label}",
        "",
        f"_{span}. Deterministic local sources only (notes, tasks, git). "
        "The skill enriches this with Granola meetings + the evidence store, then drafts "
        "the review. This file is raw material for a human to shape — not a verdict._",
        "",
    ]

    # --- Wins first (neurodivergent-first: surface what went well up top). ---
    lines.append("## Wins so far")
    if tasks["wins"]:
        for t in tasks["wins"]:
            lines.append(f"- ✅ {t['title']} [{t.get('category', 'Other')}]")
        lines.append("_(completed tasks; the store has no completion date, so these are "
                     "all-time wins surfaced for the review, not quarter-scoped)_")
    else:
        lines.append("_No completed tasks recorded yet — plenty of the quarter still ahead._")
    lines.append("")

    # --- Task activity created in range, by category. ---
    lines.append("## Tasks picked up this quarter")
    if tasks["created"]:
        for category in CATEGORIES:
            group = tasks["created"].get(category)
            if not group:
                continue
            lines.append(f"\n**{category}**")
            for t in group:
                due = f" — due {t['due_date']}" if t.get("due_date") else ""
                lines.append(f"- #{t['id']} {t['title']}{due}  · _{t.get('source', 'chat')}_")
    else:
        lines.append("_Nothing new captured in range._")
    lines.append("")

    # --- Notes digest, per cadence. ---
    lines.append("## From your notes")
    if notes:
        for cadence in ("monthly", "weekly", "daily"):
            entries = notes.get(cadence)
            if not entries:
                continue
            lines.append(f"\n### {cadence.capitalize()} notes ({len(entries)})")
            for e in entries:
                lines.append(f"\n**{e['date'].isoformat()} — {e['title']}**")
                if not e["sections"]:
                    lines.append("- _(no intentions/reflection written)_")
                for title, body in e["sections"].items():
                    lines.append(f"- _{title}_")
                    for item in body:
                        lines.append(f"  - {item}")
    else:
        lines.append("_No dated notes found in range._")
    lines.append("")

    # --- Git activity. ---
    lines.append("## What the repo shows")
    if git["count"]:
        lines.append(f"- {git['count']} commit(s) in range.")
        if git["notable"]:
            lines.append("- Notable:")
            for c in git["notable"]:
                lines.append(f"  - `{c['hash']}` {c['date']} — {c['subject']}")
    else:
        lines.append("_No commits in range (or git unavailable)._")
    lines.append("")

    # --- Handoff to the enrichment + synthesis half of the skill. ---
    lines.append("## Still to fold in (needs MCP at runtime — see SKILL.md)")
    lines.append("- Granola meetings in range (summaries, decisions, action items).")
    lines.append("- Evidence-store / daily-notes items in range (discovered via ToolSearch).")
    lines.append("- Then synthesise the DRAFT review (accomplishments, themes, meetings, "
                 "what changed, open threads) in Adam's voice, for him to edit.")
    lines.append("")

    return "\n".join(lines) + "\n"


def write_digest(label: str, digest: str) -> Path:
    """Write the digest to data/reviews/<label>.md (creating the directory if needed)."""
    out = repo_root() / "data" / "reviews" / f"{label}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(digest, encoding="utf-8")
    return out


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Assemble quarterly-review raw material.")
    p.add_argument("--from", dest="start", default=None,
                   help="ISO start date (default: first day of current quarter)")
    p.add_argument("--to", dest="end", default=None,
                   help="ISO end date (default: last day of current quarter)")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    today = date.today()
    q_start, q_end, label = quarter_bounds(today)
    start = date.fromisoformat(args.start) if args.start else q_start
    end = date.fromisoformat(args.end) if args.end else q_end
    # If a custom range doesn't line up with the current quarter, label by the start date's
    # quarter so the output filename still reads sensibly.
    if args.start or args.end:
        _, _, label = quarter_bounds(start)

    digest = build_digest(start, end, label)
    out = write_digest(label, digest)
    print(digest)
    print(f"\n_(review digest: {out.relative_to(repo_root())})_")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
