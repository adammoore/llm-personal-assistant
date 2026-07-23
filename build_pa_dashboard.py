#!/usr/bin/env python3
"""build_pa_dashboard — render the PA's central-overview dashboard (the "command deck").

Adam's ONE central space: everything relevant at a glance — a stat bar, then compact,
collapsible cards for today's dates, tasks, messages, and recent activity. Interactive:
add a task and tap-to-complete from the page. Distinct from the CIDER dashboard (deep focus
on the case); the PA *surfaces* case-relevant items for visibility but never generates legal
work-product or writes into CIDER.

Design: an ADHD-friendly instrument panel — monospace figures, one teal accent, masonry cards
that collapse (state persisted), theme-aware. Not a long linear scroll.

Output: data/PA_DASHBOARD.html (git-ignored — private).
"""

from __future__ import annotations

import html
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.activity import unified  # noqa: E402
from lib.comms import ACCOUNTS, calendar_events, fetch_inbox, partition_inbox  # noqa: E402
from lib.mailsummary import load_summary  # noqa: E402
from lib.people import load_people, reconnect_due  # noqa: E402
from lib.people import upcoming_birthdays as people_birthdays  # noqa: E402
from lib.taskstore import CATEGORIES, load_tasks, repo_root  # noqa: E402

CATEGORY_COLOR = {
    "Work": "#2E75B6", "Personal": "#7C5CBF", "Health": "#3FA796",
    "Finance": "#C08A2E", "Other": "#7A8290",
}
_ACTIVITY_GLYPH = {"task": "◇", "calendar": "▣", "mail": "✉", "file": "▢", "work": "◈"}

# The work-pull cache (skills/work-pull/pull.py --cache) drives the Work (Westminster) card.
_WORK_CACHE = Path(__file__).resolve().parent / "data" / "work_cache.json"


# Context is derived (a predictable lens, not a per-item field) — see DESIGN.md / ADR-003.
_WORK_THEMES = {"enact", "zigzag", "notch8", "westminster", "work"}
_CASE_THEMES = {"case", "court", "fdr", "hearing", "family", "cider"}


def _ctx(theme: str | None, category: str | None) -> str:
    """Derive a task/activity's context: case | work | personal (predictable, keyword-based)."""
    t = (theme or "").lower()
    if t in _CASE_THEMES:
        return "case"
    if t in _WORK_THEMES or category == "Work":
        return "work"
    return "personal"


def _esc(s: str) -> str:
    return html.escape(str(s))


def _sel(name: str, options: list[str], current: str | None) -> str:
    """A <select> with `current` pre-selected."""
    opts = "".join(f'<option{" selected" if o == current else ""}>{_esc(o)}</option>'
                   for o in options)
    return f'<select name="{name}">{opts}</select>'


def _due_state(due: str | None, today: date) -> str:
    if not due:
        return "none"
    try:
        d = date.fromisoformat(due)
    except ValueError:
        return "none"
    return "overdue" if d < today else "today" if d == today else "soon"


def _card(key: str, title: str, count: str, body: str, *, collapsed: bool = False) -> str:
    """A collapsible masonry card. `count` is a short figure shown in the header."""
    cls = "card collapsed" if collapsed else "card"
    cnt = f'<span class="cnt">{_esc(count)}</span>' if count else ""
    return (f'<section class="{cls}" data-key="{_esc(key)}">'
            f'<header class="card-h"><span class="ttl">{_esc(title)}</span>{cnt}'
            f'<span class="chev">▾</span></header>'
            f'<div class="card-b">{body}</div></section>')


def _work_events_for(day_iso: str) -> list[dict]:
    """Westminster Outlook events for a given ISO day, from the work-pull cache."""
    try:
        data = json.loads(_WORK_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [e for e in data.get("calendar_events", []) if e.get("date") == day_iso]


def _today_card(today: date) -> str:
    blocks, total = [], 0
    for acct in ACCOUNTS:
        evs = calendar_events(acct["cal"], today, today)
        if not evs:
            continue
        total += len(evs)
        evs.sort(key=lambda e: (e.get("when") or ""))
        rows = "".join(
            f'<li class="row"><span class="when">{_esc(e["when"])}</span>'
            f'<span class="what">{_esc(e["title"])}</span></li>' for e in evs)
        blocks.append(f'<div class="sub">{_esc(acct["id"])}</div><ul class="rows">{rows}</ul>')
    # Westminster (Outlook) events come from the work-pull cache, not gog/Google calendars.
    work_evs = _work_events_for(today.isoformat())
    if work_evs:
        total += len(work_evs)
        rows = "".join(
            f'<li class="row"><span class="when">{_esc(e["start"])}</span>'
            f'<span class="what">{_esc(e["title"])}</span></li>' for e in work_evs)
        blocks.append(f'<div class="sub">westminster</div><ul class="rows">{rows}</ul>')
    body = "".join(blocks) or '<p class="empty">Nothing scheduled.</p>'
    return _card("today", "Today", str(total) if total else "", body)


_PRIO_RANK = {"high": 0, "normal": 1, "low": 2}


def _urgency_band(due: str | None, today: date) -> str:
    """Spatial vertical axis: now | next (1-3d) | soon (2wk) | someday (undated/far)."""
    if not due:
        return "someday"
    try:
        d = date.fromisoformat(due)
    except ValueError:
        return "someday"
    delta = (d - today).days
    if delta <= 0:
        return "now"
    if delta <= 3:
        return "next"
    if delta <= 14:
        return "soon"
    return "someday"


def _task_li(t: dict, today: date) -> str:
    """One task <li> — shared by the category grid and the spatial urgency view.

    Carries data-state / data-theme / data-context / data-priority so facets and the spatial
    view can encode meaning (urgency=band, need=size via priority, context=colour) with CSS.
    """
    category = t.get("category") or "Other"
    accent = CATEGORY_COLOR.get(category, CATEGORY_COLOR["Other"])
    st = _due_state(t.get("due_date"), today)
    due = ""
    if t.get("due_date"):
        lbl = {"overdue": "overdue", "today": "today", "soon": t["due_date"]}[st]
        due = f'<span class="due due-{st}">{_esc(lbl)}</span>'
    flag = '<span class="flag">‼</span>' if t.get("priority") == "high" else ""
    eff = f'<span class="eff">{_esc(t.get("energy", "medium"))}</span>'
    steps = t.get("steps") or []
    steps_html = ""
    if steps:
        items = "".join(
            f'<li class="next-step">{_esc(s)}</li>' if i == 0 else f"<li>{_esc(s)}</li>"
            for i, s in enumerate(steps))
        steps_html = f'<ol class="steps">{items}</ol>'
    edit_form = (
        f'<form class="edit" method="post" action="/edit" hidden>'
        f'<input type="hidden" name="id" value="{t["id"]}">'
        f'<input name="title" value="{_esc(t["title"])}">'
        f'{_sel("category", CATEGORIES, category)}'
        f'<input name="theme" value="{_esc(t.get("theme") or "")}" placeholder="theme">'
        f'{_sel("priority", ["high", "normal", "low"], t.get("priority"))}'
        f'{_sel("energy", ["low", "medium", "high"], t.get("energy"))}'
        f'<input name="due" value="{_esc(t.get("due_date") or "")}" placeholder="due YYYY-MM-DD">'
        f'<button>Save</button></form>')
    return (
        f'<li class="task" data-state="{st}" '
        f'data-priority="{_esc(t.get("priority") or "normal")}" '
        f'data-theme="{_esc((t.get("theme") or "").lower())}" '
        f'data-context="{_ctx(t.get("theme"), category)}" style="--accent:{accent}">'
        f'<div class="t-row"><span class="dot"></span>'
        f'<span class="t-body">{flag}{_esc(t["title"])} {due}{eff}</span>'
        f'<button type="button" class="edit-btn" title="edit">✎</button>'
        f'<form class="mtd" method="post" action="/breakdown">'
        f'<input type="hidden" name="id" value="{t["id"]}">'
        f'<input type="hidden" name="spice" class="spice-in" value="3">'
        f'<button title="break it down">✨</button></form>'
        f'<form class="done" method="post" action="/complete">'
        f'<input type="hidden" name="id" value="{t["id"]}">'
        f'<button title="done">✓</button></form>'
        f'<form class="del" method="post" action="/delete">'
        f'<input type="hidden" name="id" value="{t["id"]}">'
        f'<button title="delete">🗑</button></form>'
        f'</div>{edit_form}{steps_html}</li>')


def _tasks_card(today: date, open_tasks: list[dict]) -> str:
    if not open_tasks:
        return _card("tasks", "Tasks", "", '<p class="empty">Clear slate. ✨</p>')

    # Grid grouping: by category (the predictable default).
    cat = []
    for category in CATEGORIES:
        grp = [t for t in open_tasks if (t.get("category") or "Other") == category]
        if not grp:
            continue
        grp.sort(key=lambda x: (x.get("due_date") or "9999", x["id"]))
        cat.append(f'<div class="sub">{_esc(category)}</div>'
                   f'<ul class="tasks">{"".join(_task_li(t, today) for t in grp)}</ul>')
    cat_html = f'<div class="grouping cat">{"".join(cat)}</div>'

    # Spatial grouping: by urgency band (height = urgency). Same tasks, meaning from position.
    urg = []
    for key, label in (("now", "Now"), ("next", "Next · 1–3 days"),
                       ("soon", "Soon · 2 weeks"), ("someday", "Someday")):
        grp = [t for t in open_tasks if _urgency_band(t.get("due_date"), today) == key]
        if not grp:
            continue
        grp.sort(key=lambda x: (_PRIO_RANK.get(x.get("priority"), 1),
                                x.get("due_date") or "9999", x["id"]))
        urg.append(f'<div class="band" data-band="{key}"><div class="band-h">{_esc(label)}'
                   f'<span class="band-n">{len(grp)}</span></div>'
                   f'<ul class="tasks">{"".join(_task_li(t, today) for t in grp)}</ul></div>')
    urg_html = f'<div class="grouping urg">{"".join(urg)}</div>'

    return _card("tasks", "Tasks", str(len(open_tasks)), cat_html + urg_html)


def _msg_row(m: dict, hidden: bool = False) -> str:
    cls = "row hx" if hidden else "row"
    return (f'<li class="{cls}"><span class="mk">{"•" if m["unread"] else "◦"}</span>'
            f'<span class="what"><b>{_esc(m["from"])}</b> {_esc(m["subject"][:52])}</span></li>')


def _messages_card(worth_by_acct: dict) -> str:
    blocks, total = [], 0
    for acct in ACCOUNTS:
        worth, noise = worth_by_acct[acct["id"]]
        total += len(worth)
        if not worth:
            blocks.append(f'<div class="sub">{_esc(acct["id"])}</div>'
                          f'<p class="empty sm">nothing standing out ({noise} quiet)</p>')
            continue
        vis = "".join(_msg_row(m) for m in worth[:4])
        hid = "".join(_msg_row(m, hidden=True) for m in worth[4:])
        more = (f'<li class="row more" role="button" data-n="{len(worth) - 4}">'
                f'+{len(worth) - 4} more</li>') if len(worth) > 4 else ""
        blocks.append(f'<div class="sub">{_esc(acct["id"])}</div>'
                      f'<ul class="rows">{vis}{hid}{more}</ul>')
    # Auto-summary: cached digest (if any) + a re-summarise button.
    summary = load_summary()
    sum_html = ""
    if summary:
        sum_html = (f'<div class="mail-sum">{_esc(summary["summary"])}'
                    f'<div class="sum-at">as of {_esc(summary["at"])}</div></div>')
    btn = ('<form class="sum-btn" method="post" action="/summarize-mail">'
           '<button title="summarise the inbox">✨ summarise</button></form>')
    return _card("messages", "Messages", str(total), btn + sum_html + "".join(blocks))


def _activity_card() -> str:
    stream = unified(days=14)
    if not stream:
        return ""
    rows = "".join(
        f'<li class="row" data-theme="{_esc((a.theme or "").lower())}" '
        f'data-context="{_ctx(a.theme, None)}">'
        f'<span class="when">{_esc((a.timestamp or "")[:16])}</span>'
        f'<span class="what">{_ACTIVITY_GLYPH.get(a.source, "·")} {_esc(a.title[:56])}</span></li>'
        for a in stream[:16])
    return _card("activity", "Recent activity", "", f'<ul class="rows">{rows}</ul>',
                 collapsed=True)


def _work_card() -> str:
    """Work (Westminster) card from the work-pull cache — labels + snippets + freshness.

    Defensive: no cache (never pulled) → a prompt; cache with up=false → a "launch Chrome"
    note; up=true → each surface's label and a short snippet, plus a subtle "as of <at>".
    """
    try:
        data = json.loads(_WORK_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None

    if not data:
        body = ('<p class="empty sm">No work snapshot yet — hit '
                '<b>pull work</b> to read the Enact tabs.</p>')
        return _card("work", "Work (Westminster)", "", body, collapsed=True)

    at = _esc(data.get("at") or "")
    if not data.get("up"):
        note = data.get("note") or "Enact Chrome not running — launch it."
        body = (f'<p class="empty sm">{_esc(note)}</p>'
                + (f'<div class="sum-at">as of {at}</div>' if at else ""))
        return _card("work", "Work (Westminster)", "", body, collapsed=True)

    sources = [s for s in (data.get("sources") or []) if isinstance(s, dict)]
    cal_evs = data.get("calendar_events") or []
    rows = []
    for src in sources:
        label = src.get("label") or "Work"
        if src.get("id") == "calendar" and cal_evs:
            # Render real events as a list, not a truncated one-line snippet.
            lis = "".join(
                f'<li class="row"><span class="when">{_esc(e["date"][5:])} {_esc(e["start"])}</span>'
                f'<span class="what">{_esc(e["title"])}</span></li>' for e in cal_evs[:12])
            rows.append(f'<div class="sub">{_esc(label)}</div><ul class="rows">{lis}</ul>')
            continue
        text = (src.get("text") or "").strip()
        snippet = " ".join(text.split())[:120] if text else "(tab not open)"
        rows.append(f'<div class="sub">{_esc(label)}</div>'
                    f'<p class="work-snip">{_esc(snippet)}</p>')
    body = ("".join(rows) or '<p class="empty sm">No surfaces read.</p>')
    if at:
        body += f'<div class="sum-at">as of {at}</div>'
    count = str(sum(1 for s in sources if (s.get("text") or "").strip()))
    return _card("work", "Work (Westminster)", count, body, collapsed=True)


def _people_card() -> str:
    """People — reconnect nudges + upcoming birthdays from the local people store."""
    total = len(load_people())
    btn = ('<form class="sum-btn" method="post" action="/sync-people">'
           '<button title="refresh people from your mail contacts">↻ sync from mail</button></form>')
    if not total:
        body = (btn + '<p class="empty sm">No people yet — <b>sync from mail</b> to populate '
                'from who actually emails you. (Full Monica CRM optional — MONICA_SETUP.md.)</p>')
        return _card("people", "People", "", body, collapsed=True)
    blocks = [btn]
    bdays = people_birthdays(days=45)
    if bdays:
        rows = "".join(
            f'<li class="row person" data-person="{_esc(b["name"])}" role="button" tabindex="0">'
            f'<span class="when">{b["in_days"]}d</span>'
            f'<span class="what">🎂 {_esc(b["name"])}</span></li>' for b in bdays)
        blocks.append(f'<div class="sub">birthdays</div><ul class="rows">{rows}</ul>')
    recon = reconnect_due(days=30)[:6]
    if recon:
        rows = "".join(
            f'<li class="row person" data-person="{_esc(r["name"])}" role="button" tabindex="0">'
            f'<span class="when">{r["days"]}d</span>'
            f'<span class="what">{_esc(r["name"])}</span></li>' for r in recon)
        blocks.append(f'<div class="sub">not heard from</div><ul class="rows">{rows}</ul>')
    # All tracked people (so any of them can be clicked to open their thread).
    everyone = sorted(load_people(), key=lambda p: p.get("name", ""))
    chips = "".join(
        f'<button class="person-chip" data-person="{_esc(p["name"])}">{_esc(p["name"])}</button>'
        for p in everyone)
    blocks.append(f'<div class="sub">everyone</div><div class="people-chips">{chips}</div>')
    if not bdays and not recon:
        blocks.append(f'<p class="empty sm">{total} people tracked — nothing needs you.</p>')
    return _card("people", "People", str(total), "".join(blocks), collapsed=True)


def _render_html(today: date) -> str:
    tasks = load_tasks()
    open_tasks = [t for t in tasks if not t.get("completed")]
    done_tasks = [t for t in tasks if t.get("completed")]
    due_today = sum(1 for t in open_tasks
                    if _due_state(t.get("due_date"), today) == "today")
    overdue = sum(1 for t in open_tasks
                  if _due_state(t.get("due_date"), today) == "overdue")

    worth_by_acct = {a["id"]: partition_inbox(fetch_inbox(a["mail"])) for a in ACCOUNTS}
    new_mail = sum(len(w) for w, _ in worth_by_acct.values())

    # Next meeting across both calendars over the next 2 days.
    next_mtg = "—"
    upcoming = []
    for acct in ACCOUNTS:
        for e in calendar_events(acct["cal"], today, today + timedelta(days=2)):
            if e.get("when") and e["when"] != "all day":
                upcoming.append((e.get("date", ""), e["when"], e["title"]))
    upcoming.sort()
    if upcoming:
        d, w, t = upcoming[0]
        when = w if d == today.isoformat() else f"{d[5:]} {w}"
        next_mtg = f"{when}  {t[:22]}"

    # Each chip is actionable: task chips filter the Tasks card; the others jump to a card.
    stats = [
        ("open", str(len(open_tasks)), False, "filter:all"),
        ("due today", str(due_today), due_today > 0, "filter:today"),
        ("overdue", str(overdue), overdue > 0, "filter:overdue"),
        ("new mail", str(new_mail), False, "scroll:messages"),
    ]
    deck = "".join(
        f'<button class="stat{" alert" if alert else ""}" data-act="{act}">'
        f'<span class="n">{_esc(n)}</span><span class="l">{_esc(lbl)}</span></button>'
        for lbl, n, alert, act in stats)
    deck += (f'<button class="stat next" data-act="scroll:today">'
             f'<span class="n">{_esc(next_mtg)}</span><span class="l">next</span></button>')

    wins = f' · ✓ {len(done_tasks)} done' if done_tasks else ""
    cards = (_today_card(today) + _tasks_card(today, open_tasks)
             + _messages_card(worth_by_acct) + _work_card() + _people_card() + _activity_card())

    # Facet bar — one calm row, one active facet at a time, each pivot single-focus (DESIGN.md).
    themes = sorted({t["theme"] for t in open_tasks if t.get("theme")})
    theme_chips = "".join(
        f'<button data-facet="theme:{_esc(th.lower())}">#{_esc(th)}</button>' for th in themes)
    facet_bar = (
        '<div class="facets"><button class="facet-on" data-facet="all">all</button>'
        '<span class="fg">source</span>'
        '<button data-facet="key:today">dates</button>'
        '<button data-facet="key:tasks">tasks</button>'
        '<button data-facet="key:messages">mail</button>'
        '<button data-facet="key:work">work</button>'
        '<button data-facet="key:people">people</button>'
        '<button data-facet="key:activity">activity</button>'
        + (f'<span class="fg">theme</span>{theme_chips}' if theme_chips else "")
        + '<span class="fg">context</span>'
        '<button data-facet="context:personal">personal</button>'
        '<button data-facet="context:work">work</button>'
        '<button data-facet="context:case">case</button></div>'
    )

    return (
        "<!doctype html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Personal Assistant</title>"
        f"<style>{_STYLE}</style></head><body><main>"
        f'<header class="top"><div class="date">{_esc(today.strftime("%A %-d %B %Y"))}'
        f'{wins}</div>'
        '<div class="prefs">'
        '<button id="layout-btn" title="grid ↔ spatial map (urgency · need · context)">'
        '⊞ grid</button>'
        '<button id="theme-btn" title="cycle theme">◐ theme</button>'
        '<button id="fs-dn" title="smaller text">A−</button>'
        '<button id="fs-up" title="larger text">A+</button></div></header>'
        f'<div class="deck">{deck}</div>'
        # Two refresh affordances: rebuild the page from current data, or pull the work tabs.
        '<div class="ctl">'
        '<form method="post" action="/refresh"><button class="ghost" title="rebuild now">'
        '↻ refresh</button></form>'
        '<form method="post" action="/pull-work" class="pull">'
        '<button class="ghost" title="read the Enact work tabs (needs the Enact Chrome)">'
        'pull work</button></form>'
        '</div>'
        '<form class="capture" method="post" action="/capture">'
        '<input name="title" placeholder="Add a task…" autocomplete="off" autofocus>'
        '<input name="theme" placeholder="theme" autocomplete="off" class="theme">'
        '<select name="energy"><option value="low">low</option>'
        '<option value="medium" selected>med</option><option value="high">high</option></select>'
        '<select name="priority"><option value="high">high</option>'
        '<option value="normal" selected>normal</option><option value="low">low</option></select>'
        '<button>Add</button>'
        '<label class="spice" title="✨ breakdown detail (goblin.tools spiciness)">🌶'
        '<select id="spice"><option value="1">1</option><option value="2">2</option>'
        '<option value="3" selected>3</option><option value="4">4</option>'
        '<option value="5">5</option></select></label>'
        '</form>'
        f'{facet_bar}'
        '<div id="thread" class="thread" hidden></div>'
        f'<div class="grid">{cards}</div>'
        '<footer>Central overview · CIDER is your focus space · private</footer>'
        f"</main><script>{_SCRIPT}</script></body></html>"
    )


_STYLE = """
:root{ --bg:#f4f6f8; --card:#fff; --ink:#19212b; --muted:#66707c; --line:#e4e8ec;
  --accent:#0f766e; --overdue:#a1553c; --today:#0f766e;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,monospace;
  /* Subtle, muted domain hues — colour for meaning, never alarm/clash (DESIGN.md). */
  --c-dates:#5b74b8; --c-tasks:#2f9e8f; --c-mail:#8a6bb0; --c-work:#c0894a;
  --c-activity:#7c8592; --c-personal:#8a6bb0; --c-workctx:#c0894a; --c-case:#b46a54;
  --c-people:#b0708a; }
/* Auto dark (unless the user has explicitly chosen light) */
@media (prefers-color-scheme:dark){ :root:not([data-theme=light]){ --bg:#0e1116; --card:#161b22;
  --ink:#e6e9ee; --muted:#8994a2; --line:#232a33; --accent:#2dd4bf; --overdue:#e8917a;
  --today:#2dd4bf; } }
/* Explicit user overrides (persisted) — individual variation is large (see DESIGN.md) */
:root[data-theme=dark]{ --bg:#0e1116; --card:#161b22; --ink:#e6e9ee; --muted:#8994a2;
  --line:#232a33; --accent:#2dd4bf; --overdue:#e8917a; --today:#2dd4bf; }
*{ box-sizing:border-box; }
/* Root font-size is user-adjustable; components use rem so all text scales together (≥16px). */
html{ font-size:16.5px; }
body{ margin:0; padding:1.4rem 1.1rem 3rem; background:var(--bg); color:var(--ink);
  font-size:1rem; line-height:1.6;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
main{ max-width:1100px; margin:0 auto; }
.top{ display:flex; align-items:center; gap:.6rem; }
.top .date{ font:.72rem/1 var(--mono); letter-spacing:.08em; text-transform:uppercase;
  color:var(--muted); }
.deck{ display:flex; flex-wrap:wrap; gap:.5rem; margin:.6rem 0 1rem; }
.stat{ display:flex; flex-direction:column; gap:.2rem; padding:.5rem .8rem; min-width:5rem;
  background:var(--card); border:1px solid var(--line); border-radius:12px; cursor:pointer;
  text-align:left; color:inherit; font:inherit; }
.stat:hover{ border-color:var(--accent); }
.stat.on{ border-color:var(--accent); box-shadow:inset 0 0 0 1px var(--accent); }
.stat .n{ font:650 1.2rem/1 var(--mono); font-variant-numeric:tabular-nums; }
.stat .l{ font:.6rem/1 var(--mono); letter-spacing:.09em; text-transform:uppercase;
  color:var(--muted); }
.stat.alert .n{ color:var(--overdue); }
.stat.next{ flex:1 1 12rem; }
.stat.next .n{ font-size:.86rem; font-weight:600; padding-top:.15rem; }
.capture{ display:flex; gap:.45rem; margin:0 0 1.1rem; flex-wrap:wrap; }
.capture input,.capture select,.capture button{ padding:.5rem .7rem; border:1px solid var(--line);
  border-radius:10px; background:var(--card); color:var(--ink); font-size:.9rem; }
.capture input[name=title]{ flex:1 1 12rem; }
.capture .theme{ flex:0 0 6.5rem; }
.capture button{ cursor:pointer; font-weight:650; border-color:var(--accent); color:var(--accent); }
.capture .spice{ display:inline-flex; align-items:center; gap:.3rem; font-size:.82rem;
  color:var(--muted); }
.ctl{ display:flex; gap:.45rem; margin:0 0 .8rem; }
.ctl form{ margin:0; }
.ctl .ghost{ cursor:pointer; font:.78rem/1 var(--mono); padding:.4rem .7rem; border-radius:10px;
  border:1px solid var(--line); background:var(--card); color:var(--muted); letter-spacing:.04em; }
.ctl .ghost:hover{ border-color:var(--accent); color:var(--accent); }
.ctl .pull button:disabled{ opacity:.55; cursor:progress; }
.work-snip{ margin:.15rem 0 .4rem; font-size:.84rem; color:var(--muted);
  overflow:hidden; text-overflow:ellipsis; }
.grid{ columns:330px; column-gap:14px; }
.card{ break-inside:avoid; background:var(--card); border:1px solid var(--line);
  border-radius:14px; margin:0 0 14px; overflow:hidden; }
.card-h{ display:flex; align-items:center; gap:.5rem; padding:.6rem .85rem; cursor:pointer;
  user-select:none; }
.card-h .ttl{ font:650 .7rem/1 var(--mono); letter-spacing:.1em; text-transform:uppercase;
  color:var(--ink); }
.card-h .cnt{ font:.7rem/1 var(--mono); color:var(--muted); padding:.1rem .4rem;
  border:1px solid var(--line); border-radius:999px; }
.card-h .chev{ margin-left:auto; color:var(--muted); font-size:.7rem; transition:transform .15s; }
.card.collapsed .chev{ transform:rotate(-90deg); }
.card.collapsed .card-b{ display:none; }
.card-b{ padding:.1rem .85rem .7rem; }
.sub{ font:.62rem/1 var(--mono); letter-spacing:.06em; text-transform:uppercase;
  color:var(--muted); margin:.6rem 0 .3rem; }
.rows,.tasks{ list-style:none; margin:0; padding:0; }
.row{ display:flex; gap:.55rem; padding:.28rem 0; border-top:1px solid var(--line); font-size:.9rem; }
.row:first-child{ border-top:none; }
.when{ flex:0 0 auto; min-width:4.6rem; color:var(--muted); font:.8rem/1.4 var(--mono);
  font-variant-numeric:tabular-nums; }
.mk{ flex:0 0 auto; width:.8rem; color:var(--muted); line-height:1.5; }
.what{ flex:1 1 auto; min-width:0; }
.row.more{ color:var(--accent); font-size:.78rem; padding-left:1.35rem; cursor:pointer; }
.rows .hx{ display:none; }
.rows.open .hx{ display:flex; }
.sum-btn{ margin:0 0 .5rem; }
.sum-btn button{ cursor:pointer; font-size:.78rem; padding:.25rem .6rem; border-radius:8px;
  border:1px solid var(--line); background:transparent; color:var(--accent); }
.mail-sum{ white-space:pre-wrap; font-size:.85rem; background:var(--bg); border:1px solid var(--line);
  border-radius:10px; padding:.5rem .65rem; margin:0 0 .6rem; }
.sum-at{ color:var(--muted); font:.68rem/1 var(--mono); margin-top:.35rem; }
.task{ padding:.3rem 0; border-top:1px solid var(--line); font-size:.9rem; }
.task:first-child{ border-top:none; }
.t-row{ display:flex; align-items:center; gap:.55rem; }
.dot{ flex:0 0 auto; width:8px; height:8px; border-radius:50%; background:var(--accent); }
.t-body{ flex:1 1 auto; min-width:0; }
ol.steps{ margin:.3rem 0 .25rem 1.6rem; padding:0; color:var(--muted); font-size:.82rem; }
ol.steps li{ padding:.08rem 0; }
.mtd{ margin:0; flex:0 0 auto; }
.mtd button{ cursor:pointer; width:1.7rem; height:1.7rem; border-radius:50%;
  border:1px solid var(--line); background:transparent; line-height:1; }
.mtd button:hover{ border-color:var(--accent); }
.edit-btn{ cursor:pointer; flex:0 0 auto; width:1.7rem; height:1.7rem; border-radius:50%;
  border:1px solid var(--line); background:transparent; color:var(--muted); line-height:1; }
.edit-btn:hover{ color:var(--accent); border-color:var(--accent); }
.edit{ display:flex; flex-wrap:wrap; gap:.35rem; margin:.4rem 0 .25rem 1.4rem; }
.edit[hidden]{ display:none; }
.edit input,.edit select,.edit button{ padding:.3rem .5rem; border:1px solid var(--line);
  border-radius:8px; background:var(--card); color:var(--ink); font-size:.82rem; }
.edit input[name=title]{ flex:1 1 10rem; }
.edit button{ cursor:pointer; color:var(--accent); border-color:var(--accent); font-weight:650; }
.flag{ color:var(--overdue); font-weight:700; margin-right:.15rem; }
.due{ font:.68rem/1 var(--mono); padding:.08rem .4rem; border:1px solid var(--line);
  border-radius:999px; color:var(--muted); margin-left:.2rem; }
.due-overdue{ color:var(--overdue); border-color:var(--overdue); }
.due-today{ color:var(--today); border-color:var(--today); }
.eff{ font:.66rem/1 var(--mono); color:var(--muted); margin-left:.35rem; }
.done,.del{ margin:0; flex:0 0 auto; }
.done button,.del button{ cursor:pointer; width:1.7rem; height:1.7rem; border-radius:50%;
  border:1px solid var(--line); background:transparent; color:var(--muted); line-height:1;
  font-size:.85rem; }
.done button:hover{ color:var(--accent); border-color:var(--accent); }
.del button:hover{ color:var(--overdue); border-color:var(--overdue); }
.empty{ color:var(--muted); font-size:.88rem; padding:.4rem 0; }
.empty.sm{ padding:.15rem 0; font-size:.82rem; }
footer{ color:var(--muted); font:.7rem/1 var(--mono); text-align:center; margin-top:1.5rem; }
/* No motion by default beyond a tiny chevron turn; honour reduced-motion fully. */
@media (prefers-reduced-motion:reduce){ *{ transition:none !important; animation:none !important; } }
.prefs{ display:flex; gap:.3rem; align-items:center; margin-left:auto; }
.prefs button{ cursor:pointer; font:.72rem/1 var(--mono); padding:.25rem .5rem; border-radius:8px;
  border:1px solid var(--line); background:transparent; color:var(--muted); }
.prefs button:hover{ color:var(--accent); border-color:var(--accent); }
.next-step{ color:var(--accent); font-weight:600; }
.facets{ display:flex; flex-wrap:wrap; align-items:center; gap:.35rem; margin:0 0 1rem; }
.facets .fg{ font:.6rem/1 var(--mono); letter-spacing:.08em; text-transform:uppercase;
  color:var(--muted); margin-left:.5rem; }
.facets button{ cursor:pointer; font-size:.82rem; padding:.25rem .65rem; border-radius:999px;
  border:1px solid var(--line); background:transparent; color:var(--ink); }
.facets button:hover{ border-color:var(--accent); color:var(--accent); }
.facets button.facet-on{ background:var(--accent); color:var(--bg); border-color:var(--accent); }
/* Subtle per-card domain colour: a thin coloured top edge + a tinted title. */
.card[data-key=today]{ border-top:3px solid var(--c-dates); }
.card[data-key=today] .ttl{ color:var(--c-dates); }
.card[data-key=tasks]{ border-top:3px solid var(--c-tasks); }
.card[data-key=tasks] .ttl{ color:var(--c-tasks); }
.card[data-key=messages]{ border-top:3px solid var(--c-mail); }
.card[data-key=messages] .ttl{ color:var(--c-mail); }
.card[data-key=work]{ border-top:3px solid var(--c-work); }
.card[data-key=work] .ttl{ color:var(--c-work); }
.card[data-key=activity]{ border-top:3px solid var(--c-activity); }
.card[data-key=activity] .ttl{ color:var(--c-activity); }
.card[data-key=people]{ border-top:3px solid var(--c-people); }
.card[data-key=people] .ttl{ color:var(--c-people); }
/* Context chips carry their hue as a small dot. */
.facets button[data-facet^="context:"]{ display:inline-flex; align-items:center; gap:.35rem; }
.facets button[data-facet^="context:"]::before{ content:""; width:.5rem; height:.5rem;
  border-radius:50%; background:var(--muted); }
.facets button[data-facet="context:personal"]::before{ background:var(--c-personal); }
.facets button[data-facet="context:work"]::before{ background:var(--c-workctx); }
.facets button[data-facet="context:case"]::before{ background:var(--c-case); }
/* Spatial layout (toggle): meaning from position — height=urgency, size=need, colour=context. */
.grouping.urg{ display:none; }
body.spatial .grouping.cat{ display:none; }
body.spatial .grouping.urg{ display:block; }
.band-h{ font:.62rem/1 var(--mono); letter-spacing:.08em; text-transform:uppercase;
  color:var(--muted); margin:.6rem 0 .3rem; display:flex; align-items:center; gap:.4rem; }
.band-n{ background:var(--bg); border:1px solid var(--line); border-radius:999px;
  padding:0 .4rem; font-size:.66rem; }
.band[data-band=now] .band-h{ color:var(--overdue); }
body.spatial .task{ border-left:3px solid transparent; padding-left:.45rem; }
body.spatial .task[data-context=personal]{ border-left-color:var(--c-personal); }
body.spatial .task[data-context=work]{ border-left-color:var(--c-workctx); }
body.spatial .task[data-context=case]{ border-left-color:var(--c-case); }
body.spatial .task[data-priority=high] .t-body{ font-weight:650; font-size:1.03rem; }
body.spatial .task[data-priority=low] .t-body{ color:var(--muted); font-size:.9rem; }
/* Person-as-a-thread: click a person to filter everything to items involving them. */
.person{ cursor:pointer; }
.person:hover .what{ color:var(--c-people); }
.people-chips{ display:flex; flex-wrap:wrap; gap:.3rem; }
.person-chip{ cursor:pointer; font-size:.78rem; padding:.2rem .5rem; border-radius:999px;
  border:1px solid var(--line); background:transparent; color:var(--ink); }
.person-chip:hover{ border-color:var(--c-people); color:var(--c-people); }
.thread{ display:flex; align-items:center; gap:.5rem; margin:0 0 .9rem; padding:.4rem .7rem;
  border:1px solid var(--c-people); border-radius:10px; background:var(--card); font-size:.9rem; }
.thread b{ color:var(--c-people); }
.thread button{ cursor:pointer; margin-left:auto; font-size:.78rem; padding:.2rem .55rem;
  border-radius:8px; border:1px solid var(--line); background:transparent; color:var(--muted); }
"""

_SCRIPT = """
(function(){
  var KEY='pa-collapsed';
  var state=JSON.parse(localStorage.getItem(KEY)||'{}');
  document.querySelectorAll('.card').forEach(function(c){
    var k=c.dataset.key;
    if(k in state){ c.classList.toggle('collapsed', state[k]); }
    c.querySelector('.card-h').addEventListener('click', function(){
      c.classList.toggle('collapsed');
      state[k]=c.classList.contains('collapsed');
      localStorage.setItem(KEY, JSON.stringify(state));
    });
  });
  // Actionable stat chips: task chips filter the Tasks card; others jump to a card.
  function filterTasks(state){
    var card=document.querySelector('.card[data-key="tasks"]');
    if(!card) return;
    card.classList.remove('collapsed');
    card.querySelectorAll('.task').forEach(function(t){
      t.style.display=(!state||t.dataset.state===state)?'':'none';
    });
    card.querySelectorAll('.sub').forEach(function(sub){
      var ul=sub.nextElementSibling;
      if(ul&&ul.classList.contains('tasks')){
        var any=[].some.call(ul.querySelectorAll('.task'),function(t){return t.style.display!=='none';});
        sub.style.display=any?'':'none';
      }
    });
  }
  var current='';
  document.querySelectorAll('.stat[data-act]').forEach(function(chip){
    chip.addEventListener('click',function(){
      var act=chip.dataset.act;
      if(act.indexOf('filter:')===0){
        var st=act.slice(7); if(st==='all') st='';
        if(current===st) st='';               // click again to clear
        current=st;
        document.querySelectorAll('.stat').forEach(function(c){c.classList.remove('on');});
        if(st) chip.classList.add('on');
        filterTasks(st);
      } else if(act.indexOf('scroll:')===0){
        var c=document.querySelector('.card[data-key="'+act.slice(7)+'"]');
        if(c){ c.classList.remove('collapsed');
          var rm=matchMedia('(prefers-reduced-motion: reduce)').matches;
          c.scrollIntoView({behavior: rm?'auto':'smooth', block:'start'}); }
      }
    });
  });
  // "+N more" messages: reveal the hidden rows in that account's list.
  document.querySelectorAll('.row.more').forEach(function(m){
    m.addEventListener('click', function(){
      var ul=m.closest('.rows'); ul.classList.toggle('open');
      m.textContent = ul.classList.contains('open') ? 'less' : ('+'+m.dataset.n+' more');
    });
  });
  // ✎ edit: toggle the inline edit form for a task.
  document.querySelectorAll('.edit-btn').forEach(function(b){
    b.addEventListener('click', function(){
      var f=b.closest('.task').querySelector('.edit');
      if(f) f.hidden=!f.hidden;
    });
  });
  // ✨ Magic ToDo: carry the chosen spiciness into each breakdown, show it's working.
  document.querySelectorAll('.mtd').forEach(function(f){
    f.addEventListener('submit', function(){
      var sp=document.getElementById('spice');
      if(sp) f.querySelector('.spice-in').value=sp.value;
      var b=f.querySelector('button'); b.textContent='…'; b.disabled=true;
    });
  });
  // "pull work" is slow (drives the Enact Chrome) — show it's working and block double-posts.
  document.querySelectorAll('form.pull').forEach(function(f){
    f.addEventListener('submit', function(){
      var b=f.querySelector('button'); b.textContent='pulling…'; b.disabled=true;
    });
  });
  // Layout toggle — grid (by category) ↔ spatial map (urgency=height, need=size, context=colour).
  var lb=document.getElementById('layout-btn');
  function setLayout(sp){ document.body.classList.toggle('spatial', sp);
    localStorage.setItem('pa-spatial', sp?'1':'0');
    if(lb) lb.textContent = sp?'▤ map':'⊞ grid'; }
  if(localStorage.getItem('pa-spatial')==='1') setLayout(true);
  if(lb) lb.addEventListener('click', function(){
    setLayout(!document.body.classList.contains('spatial')); });

  // Facet bar — one active facet at a time; each pivot is single-focus (DESIGN.md).
  function applyFacet(f){
    f=f||'all';
    var cards=document.querySelectorAll('.grid .card');
    cards.forEach(function(c){ c.style.display=''; });
    document.querySelectorAll('.grid .task, .card[data-key="activity"] .row')
      .forEach(function(el){ el.style.display=''; });
    if(f!=='all'){
      if(f.indexOf('key:')===0){
        var k=f.slice(4);
        cards.forEach(function(c){ c.style.display=(c.dataset.key===k)?'':'none'; });
        var only=document.querySelector('.card[data-key="'+k+'"]');
        if(only) only.classList.remove('collapsed');
      } else {
        var parts=f.split(':'), attr=parts[0], val=parts[1];   // theme:x | context:x
        cards.forEach(function(c){
          var k=c.dataset.key;
          if(k==='tasks'||k==='activity'){ c.style.display=''; c.classList.remove('collapsed'); }
          else c.style.display='none';
        });
        document.querySelectorAll('.card[data-key="tasks"] .task, .card[data-key="activity"] .row')
          .forEach(function(el){ el.style.display=(el.dataset[attr]===val)?'':'none'; });
      }
    }
    document.querySelectorAll('.card[data-key="tasks"] .sub').forEach(function(sub){
      var ul=sub.nextElementSibling;
      if(ul&&ul.classList.contains('tasks')){
        var any=[].some.call(ul.querySelectorAll('.task'),function(t){return t.style.display!=='none';});
        sub.style.display=any?'':'none';
      }
    });
    document.querySelectorAll('.facets button').forEach(function(b){
      b.classList.toggle('facet-on', b.dataset.facet===f); });
    localStorage.setItem('pa-facet', f);
  }
  document.querySelectorAll('.facets button').forEach(function(b){
    b.addEventListener('click', function(){ applyFacet(b.dataset.facet); }); });
  var savedFacet=localStorage.getItem('pa-facet');
  if(savedFacet && savedFacet!=='all') applyFacet(savedFacet);

  // Person-as-a-thread — click a person to show everything involving them (ZigZag payoff).
  function clearThread(){
    var th=document.getElementById('thread'); if(th){ th.hidden=true; th.innerHTML=''; }
    applyFacet('all');
  }
  function focusPerson(name){
    var n=(name||'').toLowerCase(); if(!n) return;
    var cards=document.querySelectorAll('.grid .card');
    cards.forEach(function(c){ c.style.display=''; c.classList.remove('collapsed'); });
    cards.forEach(function(c){
      if(c.dataset.key==='people') return;          // keep People visible to pick another
      var visible=false;
      c.querySelectorAll('.row, .task').forEach(function(el){
        var m=el.textContent.toLowerCase().indexOf(n)!==-1;
        el.style.display=m?'':'none'; if(m) visible=true;
      });
      c.querySelectorAll('.sub').forEach(function(sub){
        var sib=sub.nextElementSibling;
        if(sib && (sib.classList.contains('rows')||sib.classList.contains('tasks'))){
          var any=[].some.call(sib.querySelectorAll('.row,.task'),
            function(x){return x.style.display!=='none';});
          sub.style.display=any?'':'none';
        }
      });
      c.style.display=visible?'':'none';
    });
    var th=document.getElementById('thread');
    if(th){ th.hidden=false;
      th.innerHTML='👤 <b></b> — everything involving them <button class="clear-thread">clear</button>';
      th.querySelector('b').textContent=name;
      th.querySelector('.clear-thread').addEventListener('click', clearThread); }
    document.querySelectorAll('.facets button').forEach(function(b){ b.classList.remove('facet-on'); });
  }
  document.querySelectorAll('[data-person]').forEach(function(el){
    el.addEventListener('click', function(){ focusPerson(el.dataset.person); });
    el.addEventListener('keydown', function(e){ if(e.key==='Enter') focusPerson(el.dataset.person); });
  });

  // Preferences (persisted): theme + text size. Individual variation is large (DESIGN.md).
  var root=document.documentElement;
  var savedTheme=localStorage.getItem('pa-theme');
  if(savedTheme && savedTheme!=='auto') root.setAttribute('data-theme', savedTheme);
  var savedFs=localStorage.getItem('pa-fs'); if(savedFs) root.style.fontSize=savedFs;
  var tb=document.getElementById('theme-btn');
  if(tb) tb.addEventListener('click', function(){
    var order=['auto','light','dark'];
    var cur=localStorage.getItem('pa-theme')||'auto';
    var next=order[(order.indexOf(cur)+1)%3];
    localStorage.setItem('pa-theme', next);
    if(next==='auto') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', next);
    tb.textContent='◐ '+next;
  });
  if(tb) tb.textContent='◐ '+(localStorage.getItem('pa-theme')||'auto');
  function setFs(px){ px=Math.max(14, Math.min(22, px)); root.style.fontSize=px+'px';
    localStorage.setItem('pa-fs', px+'px'); }
  function curFs(){ return parseFloat(getComputedStyle(root).fontSize)||16.5; }
  var up=document.getElementById('fs-up'), dn=document.getElementById('fs-dn');
  if(up) up.addEventListener('click', function(){ setFs(curFs()+1); });
  if(dn) dn.addEventListener('click', function(){ setFs(curFs()-1); });

  // Refresh so monitor updates appear — but never yank the page while you're using it.
  var lastActive=Date.now();
  ['mousemove','keydown','scroll','click'].forEach(function(e){
    document.addEventListener(e, function(){ lastActive=Date.now(); }, {passive:true});
  });
  setInterval(function(){
    if(document.hidden) return;                       // not looking — no point
    if(Date.now()-lastActive < 45000) return;         // you're active — don't interrupt
    var a=document.activeElement;
    if(a && a.closest && a.closest('.capture')) return;
    location.reload();
  }, 60000);
})();
"""


def build(output: Path | None = None, today: date | None = None) -> Path:
    """Render the dashboard to disk and return its path."""
    today = today or date.today()
    output = output or (repo_root() / "data" / "PA_DASHBOARD.html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render_html(today), encoding="utf-8")
    return output


def main() -> int:
    print(f"wrote {build()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
