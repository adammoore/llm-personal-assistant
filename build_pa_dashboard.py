#!/usr/bin/env python3
"""build_pa_dashboard — render the PA's own central-overview dashboard.

Adam's ONE central space: everything relevant in a glance — upcoming dates (both calendars,
incl. case dates), messages needing a look, and tasks. This is distinct from the CIDER
dashboard, whose job is the opposite: a calm, undisturbed space for deep focus on the case.
So the PA *surfaces* case-relevant dates/messages/tasks for visibility; it just never
generates legal work-product or writes into CIDER's data/regenerate path.

Output: data/PA_DASHBOARD.html (git-ignored — private).

Design (neurodivergent-first): calm and legible, small wins acknowledged briefly, open
work shown as an invitation — never itemised as debt. Theme-aware (light/dark).
"""

from __future__ import annotations

import html
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.activity import unified  # noqa: E402
from lib.comms import ACCOUNTS, calendar_events, fetch_inbox, partition_inbox  # noqa: E402
from lib.taskstore import CATEGORIES, load_tasks, repo_root  # noqa: E402

# Muted, calm category accents (accessible in both light and dark).
CATEGORY_COLOR = {
    "Work": "#2E75B6",
    "Personal": "#7C5CBF",
    "Health": "#3FA796",
    "Finance": "#C08A2E",
    "Other": "#7A8290",
}


def _due_state(due: str | None, today: date) -> str:
    """Classify a due date relative to today: overdue | today | soon | none."""
    if not due:
        return "none"
    try:
        d = date.fromisoformat(due)
    except ValueError:
        return "none"
    if d < today:
        return "overdue"
    if d == today:
        return "today"
    return "soon"


def _task_card(task: dict, today: date) -> str:
    """One task as an HTML list item, with a gentle due-date cue."""
    title = html.escape(task["title"])
    accent = CATEGORY_COLOR.get(task.get("category", "Other"), CATEGORY_COLOR["Other"])
    state = _due_state(task.get("due_date"), today)
    due_html = ""
    if task.get("due_date"):
        label = {"overdue": "overdue", "today": "today", "soon": task["due_date"]}[state]
        due_html = f'<span class="due due-{state}">{html.escape(label)}</span>'
    desc = task.get("description")
    desc_html = f'<div class="desc">{html.escape(desc)}</div>' if desc else ""
    return (
        f'<li class="task" style="--accent:{accent}">'
        f'<span class="cat-dot"></span>'
        f'<div class="body"><div class="title">{title}{due_html}</div>{desc_html}</div>'
        f'<form class="done-form" method="post" action="/complete">'
        f'<input type="hidden" name="id" value="{task["id"]}">'
        f'<button title="mark done" aria-label="mark done">✓</button></form>'
        f'</li>'
    )


def _event_line(ev: dict) -> str:
    """One upcoming-event row: date (+ time) and title."""
    when = html.escape(ev.get("date") or "")
    if ev.get("when") and ev["when"] != "all day":
        when += " " + html.escape(ev["when"])
    loc = f' · {html.escape(ev["location"][:34])}' if ev.get("location") else ""
    return (f'<li class="row"><span class="when">{when}</span>'
            f'<span class="what">{html.escape(ev["title"])}{loc}</span></li>')


def _upcoming_section(today: date) -> str:
    """Dates across both calendars for the next 14 days (case dates included)."""
    end = today + timedelta(days=14)
    blocks = []
    for acct in ACCOUNTS:
        evs = calendar_events(acct["cal"], today, end)
        if not evs:
            continue
        evs.sort(key=lambda e: (e.get("date") or "", e.get("when") or ""))
        items = "\n".join(_event_line(e) for e in evs[:12])
        blocks.append(f'<div class="sub">{html.escape(acct["id"])}</div>'
                      f'<ul class="rows">{items}</ul>')
    if not blocks:
        return ""
    return ('<section class="group"><h2>Upcoming<span class="count">14 days</span></h2>'
            + "".join(blocks) + "</section>")


def _messages_section() -> str:
    """Messages worth a look across both inboxes (kept separate)."""
    blocks = []
    for acct in ACCOUNTS:
        worth, noise = partition_inbox(fetch_inbox(acct["mail"]))
        if not worth:
            blocks.append(f'<div class="sub">{html.escape(acct["id"])}</div>'
                          f'<ul class="rows"><li class="row"><span class="what muted">'
                          f'nothing standing out ({noise} quiet)</span></li></ul>')
            continue
        rows = []
        for m in worth[:5]:
            dot = "•" if m["unread"] else "◦"
            rows.append(f'<li class="row"><span class="when">{dot}</span>'
                        f'<span class="what">{html.escape(m["from"])}: '
                        f'{html.escape(m["subject"][:60])}</span></li>')
        blocks.append(f'<div class="sub">{html.escape(acct["id"])}</div>'
                      f'<ul class="rows">{"".join(rows)}</ul>')
    return ('<section class="group"><h2>Needs a look<span class="count">mail</span></h2>'
            + "".join(blocks) + "</section>")


# Short glyphs so the unified stream reads at a glance without a legend.
_ACTIVITY_GLYPH = {"task": "◇", "calendar": "▣", "mail": "✉", "file": "▢"}


def _activity_section(days: int = 14) -> str:
    """A compact unified timeline across tasks, calendar, mail, and work files.

    Additive read-only view — the practical seed of the "associative trails" idea:
    everything the PA knows about on one plane, newest/soonest-first. Reuses the same
    .group/.sub/.rows/.row/.when/.what classes as the other sections.
    """
    stream = unified(days=days)
    if not stream:
        return ""
    rows = []
    # Cap the timeline so the glance stays calm rather than exhaustive.
    for a in stream[:14]:
        glyph = _ACTIVITY_GLYPH.get(a.source, "·")
        when = html.escape((a.timestamp or "")[:16])
        rows.append(
            f'<li class="row"><span class="when">{when}</span>'
            f'<span class="what">{glyph} {html.escape(a.title[:64])}</span></li>'
        )
    return ('<section class="group"><h2>Recent activity'
            '<span class="count">all sources</span></h2>'
            f'<ul class="rows">{"".join(rows)}</ul></section>')


def _render_html(tasks: list[dict], today: date) -> str:
    """Assemble the full self-contained dashboard document."""
    open_tasks = [t for t in tasks if not t.get("completed")]
    done_tasks = [t for t in tasks if t.get("completed")]
    overdue = sum(1 for t in open_tasks if _due_state(t.get("due_date"), today) == "overdue")

    # Group open tasks by the fixed category order for a stable layout.
    groups_html = []
    for category in CATEGORIES:
        group = [t for t in open_tasks if t.get("category") == category]
        if not group:
            continue
        group.sort(key=lambda x: (x.get("due_date") or "9999", x["id"]))
        items = "\n".join(_task_card(t, today) for t in group)
        groups_html.append(
            f'<section class="group"><h2>{html.escape(category)}'
            f'<span class="count">{len(group)}</span></h2>'
            f'<ul class="tasks">{items}</ul></section>'
        )

    if open_tasks:
        open_body = "\n".join(groups_html)
    else:
        open_body = '<p class="empty">Nothing open right now — a clear slate. ✨</p>'

    # Small wins: acknowledged briefly, never as a ledger.
    wins = ""
    if done_tasks:
        wins = (f'<p class="wins">✓ {len(done_tasks)} done recently — nice.</p>')

    overdue_note = ""
    if overdue:
        overdue_note = (f'<p class="gentle">{overdue} '
                        f'{"item is" if overdue == 1 else "items are"} past their date — '
                        f'no rush, just when you\'re ready.</p>')

    greeting = _greeting(today)
    return _PAGE.format(
        today=today.strftime("%A %-d %B %Y"),
        greeting=html.escape(greeting),
        open_count=len(open_tasks),
        overdue_note=overdue_note,
        wins=wins,
        upcoming_body=_upcoming_section(today),
        messages_body=_messages_section(),
        tasks_header=('<section class="group"><h2>Tasks'
                      f'<span class="count">{len(open_tasks)}</span></h2></section>'
                      if open_tasks else ""),
        open_body=open_body,
        activity_body=_activity_section(),
    )


def _greeting(today: date) -> str:
    """A light, non-demanding greeting."""
    return "Here's your day — pick what fits."


# Self-contained page: inline CSS, theme-aware, no external requests.
_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>Personal Assistant</title>
<style>
  :root {{
    --bg:#f7f8fa; --card:#ffffff; --ink:#1f2430; --muted:#6b7280; --line:#e6e8ec;
    --overdue:#b4472e; --today:#2E75B6;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:#14171c; --card:#1c2027; --ink:#e7e9ee; --muted:#9aa2af; --line:#2a2f38;
      --overdue:#e08b76; --today:#7fb2e8;
    }}
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; padding:2.2rem 1.2rem 4rem; background:var(--bg); color:var(--ink);
    font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  }}
  main {{ max-width:640px; margin:0 auto; }}
  header {{ margin-bottom:1.8rem; }}
  .date {{ color:var(--muted); font-size:.9rem; letter-spacing:.02em; }}
  h1 {{ font-size:1.5rem; margin:.25rem 0 .1rem; font-weight:650; }}
  .summary {{ color:var(--muted); font-size:.95rem; }}
  .gentle {{ color:var(--muted); font-size:.9rem; margin:.4rem 0 0; }}
  .wins {{ color:var(--today); font-size:.9rem; margin:.5rem 0 0; }}
  .group {{
    background:var(--card); border:1px solid var(--line); border-radius:14px;
    padding:1rem 1.1rem; margin:1rem 0; box-shadow:0 1px 2px rgba(0,0,0,.03);
  }}
  .group h2 {{
    font-size:.8rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted);
    margin:0 0 .6rem; display:flex; align-items:center; gap:.5rem; font-weight:650;
  }}
  .count {{
    background:var(--bg); border:1px solid var(--line); border-radius:999px;
    padding:0 .5rem; font-size:.75rem; color:var(--muted);
  }}
  ul.tasks {{ list-style:none; margin:0; padding:0; }}
  li.task {{ display:flex; gap:.7rem; padding:.5rem 0; border-top:1px solid var(--line); }}
  li.task:first-child {{ border-top:none; }}
  .cat-dot {{ flex:0 0 auto; width:9px; height:9px; border-radius:50%;
    background:var(--accent); margin-top:.55rem; }}
  .body {{ flex:1 1 auto; }}
  .title {{ display:flex; align-items:baseline; gap:.55rem; flex-wrap:wrap; }}
  .desc {{ color:var(--muted); font-size:.88rem; margin-top:.15rem; }}
  .due {{ font-size:.75rem; padding:.05rem .45rem; border-radius:999px;
    border:1px solid var(--line); color:var(--muted); }}
  .due-overdue {{ color:var(--overdue); border-color:var(--overdue); }}
  .due-today {{ color:var(--today); border-color:var(--today); }}
  .sub {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.06em;
    color:var(--muted); font-weight:650; margin:.7rem 0 .2rem; }}
  .sub:first-child {{ margin-top:0; }}
  ul.rows {{ list-style:none; margin:0; padding:0; }}
  li.row {{ display:flex; gap:.6rem; padding:.32rem 0; border-top:1px solid var(--line);
    font-size:.92rem; }}
  li.row:first-child {{ border-top:none; }}
  .when {{ flex:0 0 auto; color:var(--muted); font-variant-numeric:tabular-nums;
    min-width:5.4rem; }}
  .what {{ flex:1 1 auto; }}
  .what.muted {{ color:var(--muted); }}
  .capture {{ display:flex; gap:.5rem; margin:0 0 1.4rem; flex-wrap:wrap; }}
  .capture input, .capture select, .capture button {{ padding:.5rem .7rem;
    border:1px solid var(--line); border-radius:10px; background:var(--card);
    color:var(--ink); font-size:.92rem; }}
  .capture input[name=title] {{ flex:1 1 12rem; }}
  .capture button {{ cursor:pointer; font-weight:650; }}
  li.task {{ align-items:center; }}
  .done-form {{ margin:0; flex:0 0 auto; }}
  .done-form button {{ cursor:pointer; width:1.9rem; height:1.9rem; border-radius:50%;
    border:1px solid var(--line); background:var(--card); color:var(--muted); line-height:1; }}
  .done-form button:hover {{ color:var(--today); border-color:var(--today); }}
  .empty {{ color:var(--muted); text-align:center; padding:2rem 0; }}
  footer {{ color:var(--muted); font-size:.78rem; text-align:center; margin-top:2rem; }}
</style>
</head>
<body>
<main>
  <header>
    <div class="date">{today}</div>
    <h1>{greeting}</h1>
    <div class="summary">{open_count} open</div>
    {overdue_note}
    {wins}
  </header>
  <form class="capture" method="post" action="/capture">
    <input name="title" placeholder="Add a task…" autocomplete="off" autofocus>
    <input name="theme" placeholder="theme" autocomplete="off" style="flex:0 0 7rem">
    <select name="energy">
      <option value="low">low</option>
      <option value="medium" selected>medium</option>
      <option value="high">high</option>
    </select>
    <select name="priority">
      <option value="high">high</option>
      <option value="normal" selected>normal</option>
      <option value="low">low</option>
    </select>
    <button>Add</button>
  </form>
  {upcoming_body}
  {messages_body}
  {tasks_header}
  {open_body}
  {activity_body}
  <footer>Your central overview · CIDER is your focus space · generated locally, private</footer>
</main>
</body>
</html>
"""


def build(output: Path | None = None, today: date | None = None) -> Path:
    """Render the dashboard to disk and return its path."""
    today = today or date.today()
    tasks = load_tasks()
    output = output or (repo_root() / "data" / "PA_DASHBOARD.html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render_html(tasks, today), encoding="utf-8")
    return output


def main() -> int:
    path = build()
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
