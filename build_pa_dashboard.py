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
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.activity import unified
from lib.brief import load_brief
from lib.comms import ACCOUNTS
from lib.glance import load as glance_load
from lib.mailsummary import load_summary
from lib import cider
from lib.people import CIRCLES, load_people, ranked_people
from lib.pins import load_pins
from lib.taskstore import CATEGORIES, load_tasks, repo_root

CATEGORY_COLOR = {
    "Work": "#2E75B6", "Personal": "#7C5CBF", "Health": "#3FA796",
    "Finance": "#C08A2E", "Other": "#7A8290",
}
_ACTIVITY_GLYPH = {"task": "◇", "calendar": "▣", "mail": "✉", "file": "▢", "work": "◈",
                   "meeting": "🎙", "document": "▤"}

# The work-pull cache (skills/work-pull/pull.py --cache) drives the Work (Westminster) card.
_WORK_CACHE = Path(__file__).resolve().parent / "data" / "work_cache.json"
# Apple Reminders mirror (lib/reminders.py write_cache) — open reminders from Siri/app/WhatsApp.
_REMIND_CACHE = Path(__file__).resolve().parent / "data" / "reminders_cache.json"


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


# Loaded once per render (in _render_html) so item renderers can flag pinned state cheaply.
_PINS: dict = {"task": [], "person": [], "message": []}


def _is_pinned(kind: str, obj_id: str | int) -> bool:
    return str(obj_id) in _PINS.get(kind, [])


def _pin_btn(kind: str, obj_id: str | int, pinned: bool) -> str:
    """A ★/☆ toggle that pins a task/person/message into the Priorities card."""
    star = "★" if pinned else "☆"
    cls = "pin on" if pinned else "pin"
    title = "unpin" if pinned else "pin to priorities"
    return (f'<form class="{cls}" method="post" action="/pin">'
            f'<input type="hidden" name="kind" value="{kind}">'
            f'<input type="hidden" name="id" value="{_esc(str(obj_id))}">'
            f'<button title="{title}">{star}</button></form>')


def _card(key: str, title: str, count: str, body: str, *, collapsed: bool = False) -> str:
    """A collapsible masonry card. `count` is a short figure shown in the header."""
    cls = "card collapsed" if collapsed else "card"
    cnt = f'<span class="cnt">{_esc(count)}</span>' if count else ""
    return (f'<section class="{cls}" data-key="{_esc(key)}">'
            f'<header class="card-h"><span class="ttl">{_esc(title)}</span>{cnt}'
            f'<span class="chev">▾</span></header>'
            f'<div class="card-b">{body}</div></section>')


def _details(gid: str, label: str, body: str, *, count: int | str = "",
             open_default: bool = True, cls: str = "") -> str:
    """A collapsible group (native <details>) so each category/band/circle folds on its own.

    Default open state is a calm first impression (urgent groups open, long tails closed); the
    per-group choice then persists (localStorage, keyed by `gid`) so Adam's curation sticks.
    """
    n = f'<span class="grp-n">{_esc(str(count))}</span>' if count != "" else ""
    op = " open" if open_default else ""
    return (f'<details class="grp {cls}" data-grp="{_esc(gid)}"{op}>'
            f'<summary class="sub grp-h">{_esc(label)}{n}'
            f'<span class="grp-chev">▾</span></summary>{body}</details>')


def _is_urgent(t: dict, today: date) -> bool:
    """A task worth surfacing by default — high priority, or overdue / due today."""
    return (t.get("priority") == "high"
            or _due_state(t.get("due_date"), today) in ("overdue", "today"))


def _work_events_for(day_iso: str) -> list[dict]:
    """Westminster Outlook events for a given ISO day, from the work-pull cache."""
    try:
        data = json.loads(_WORK_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [e for e in data.get("calendar_events", []) if e.get("date") == day_iso]


def _reminders() -> list[dict]:
    """Open Apple Reminders from the mirror cache (lib/reminders.py write_cache)."""
    try:
        data = json.loads(_REMIND_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data.get("items", []) if data.get("ok") else []


def _today_card(today: date, events_by_acct: dict) -> str:
    blocks, total = [], 0
    tstr = today.isoformat()
    for acct in ACCOUNTS:
        evs = [e for e in events_by_acct.get(acct["id"], []) if e.get("date") == tstr]
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
    # Reminders due today or overdue (Apple Reminders mirror).
    tstr = today.isoformat()
    due_rem = [r for r in _reminders() if r.get("due") and r["due"][:10] <= tstr]
    if due_rem:
        total += len(due_rem)
        rows = "".join(
            f'<li class="row"><span class="when">{_esc(r["due"][:10])}</span>'
            f'<span class="what">{_esc(r["title"])}</span></li>' for r in due_rem)
        blocks.append(f'<div class="sub">reminders due</div><ul class="rows">{rows}</ul>')
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
        f'data-energy="{_esc(t.get("energy") or "medium")}" '
        f'data-est="{_esc(str(t.get("estimate_min") or 0))}" '
        f'data-context="{_ctx(t.get("theme"), category)}" style="--accent:{accent}">'
        f'<div class="t-row"><span class="dot"></span>'
        f'<span class="t-body">{flag}{_esc(t["title"])} {due}{eff}</span>'
        f'{_pin_btn("task", t["id"], _is_pinned("task", t["id"]))}'
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

    # Grid grouping: by category (the predictable default). Each category folds on its own —
    # open by default only if it holds something urgent, so the first view is calm.
    cat = []
    for category in CATEGORIES:
        grp = [t for t in open_tasks if (t.get("category") or "Other") == category]
        if not grp:
            continue
        grp.sort(key=lambda x: (x.get("due_date") or "9999", x["id"]))
        cat.append(_details(
            f"task-cat-{category}", category,
            f'<ul class="tasks">{"".join(_task_li(t, today) for t in grp)}</ul>',
            count=len(grp), open_default=any(_is_urgent(t, today) for t in grp)))
    cat_html = f'<div class="grouping cat">{"".join(cat)}</div>'

    # Spatial grouping: by urgency band. Near bands open, the long tail (Soon/Someday) folded.
    urg = []
    for key, label in (("now", "Now"), ("next", "Next · 1–3 days"),
                       ("soon", "Soon · 2 weeks"), ("someday", "Someday")):
        grp = [t for t in open_tasks if _urgency_band(t.get("due_date"), today) == key]
        if not grp:
            continue
        grp.sort(key=lambda x: (_PRIO_RANK.get(x.get("priority"), 1),
                                x.get("due_date") or "9999", x["id"]))
        urg.append(_details(
            f"task-band-{key}", label,
            f'<ul class="tasks">{"".join(_task_li(t, today) for t in grp)}</ul>',
            count=len(grp), open_default=key in ("now", "next"), cls="band"))
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


# ── The Nest: bounded, nested containers wired by visible connections ────────────────────────
# Not a dot cloud (Adam: "useless sea of dots"). The lineage is Nelson's parallel Declaration of
# Independence / Tinderbox / NoteCards FileBoxes: items live inside titled, bounded containers,
# nested by dimension (context › theme), and clicking an item TRACES its links — curved lines to
# everything it connects to (shared theme, or a person it names) across containers, transclusion
# made visible. Each item carries `data-tags` (t:<theme>, p:<person>); the wiring is client-side.
_CTX_ORDER = ("case", "work", "personal", "medical", "local-authority", "other")
_PRINCIPAL_SLUGS = frozenset({"adam", "cora", "gwen", "isaac"})  # in cider-store's graph
# Domain detection so contexts separate cleanly (else everything lands in 'personal').
_NEST_LEGAL = ("court", "hearing", "fdr", "case", "family", "legal", "lv26", "urn", "redaction",
               "solicitor", "isabella", "henry williams", "hayley", "liverpool county", "daniels",
               " cora", "gwen", "isaac", "beverley", "jmw", "form e")
_NEST_WORK = ("enact", "zigzag", "notch8", "westminster", "pathfinder", "cosector", "teams",
              "slack", "outlook", "gorc", "maldreth", "rda")
_NEST_MEDICAL = ("nhs", " gp ", "dentist", "medical", "surgery", "hospital", "health", "physio",
                 "camhs", "alder hey")
_NEST_LA = ("council", "social care", "social work", "safeguard", "sefton", "children's services")


def _nest_domain(title: str, theme: str, base_ctx: str, refs: set) -> str:
    hay = f"{title} {' '.join(refs)} {theme or ''}".lower()
    if any(k in hay for k in _NEST_LEGAL):
        return "case"
    if any(k in hay for k in _NEST_WORK):
        return "work"
    if any(k in hay for k in _NEST_MEDICAL):
        return "medical"
    if any(k in hay for k in _NEST_LA):
        return "local-authority"
    return base_ctx or "personal"


def _people_ref_index() -> list[tuple[str, str]]:
    """(match-token, person-name) pairs for spotting people named in item titles.

    Full name plus distinctive tokens (≥4 chars); 'moore' excluded — too common in this family.
    """
    idx: list[tuple[str, str]] = []
    for p in load_people():
        nm = (p.get("name") or "").strip()
        if not nm:
            continue
        idx.append((nm.lower(), nm))
        for t in nm.split():
            if len(t) >= 4 and t.lower() != "moore":
                idx.append((t.lower(), nm))
    return idx


def _field_view(today: date) -> str:
    refidx = _people_ref_index()
    nodes = []
    for a in unified(days=21)[:80]:
        low = a.title.lower()
        refs = {nm for tok, nm in refidx if tok in low}
        theme = (a.theme or "").lower()
        base = _ctx(a.theme, a.type if a.source == "task" else None)
        # Meetings arrive pre-classified (agent-tagged context) — respect it over re-derivation.
        ctx = ((a.meta or {}).get("context") if a.source == "meeting" else None) \
            or _nest_domain(a.title, theme, base, refs)
        nodes.append({"title": a.title, "kind": a.source, "theme": theme, "refs": refs,
                      "ctx": ctx})
    for p in ranked_people(set(_PINS.get("person", [])))[:40]:
        refs = {p["name"]}
        nodes.append({"title": p["name"], "kind": "person", "theme": "", "refs": refs,
                      "slug": p.get("slug"),
                      "ctx": _nest_domain(p["name"], "", p.get("context") or "personal", refs)})

    def tags(n: dict) -> str:
        # Delimited by '|' — person names contain spaces, so a space delimiter would split them.
        out = ([f"t:{n['theme']}"] if n["theme"] else []) + [f"p:{r.lower()}" for r in n["refs"]]
        if n.get("slug"):                                  # slug tag wires people ↔ cider claims
            out.append(f"s:{n['slug']}")
        return _esc("|".join(out))

    # Gated case-evidence layer: the case principals' claim graph, read from cider-store (read-only,
    # "visitation"). Off by default (the wall) — revealed by the ⚖ case toggle; Adam's private view.
    principals = {n["slug"] for n in nodes if n["kind"] == "person"
                  and n.get("slug") in _PRINCIPAL_SLUGS}
    claims: dict[str, dict] = {}
    if cider.available():
        for slug in sorted(principals):
            for cl in cider.person_claims(slug):
                e = claims.setdefault(cl["id"], {"label": cl["label"], "status": cl["status"],
                                                 "slugs": set()})
                e["slugs"].add(slug)

    def _claim_sub() -> str:
        if not claims:
            return ""
        chips = ""
        for e in claims.values():
            st = (e["status"] or "").split()[0].lower() if e["status"] else ""
            wire = "|".join(f"s:{s}" for s in sorted(e["slugs"]))
            chips += (f'<div class="fitem k-claim st-{_esc(st)}" data-tags="{_esc(wire)}" '
                      f'title="{_esc(e["label"])} [{_esc(e["status"])}]">'
                      f'⚖ {_esc(e["label"][:52])}</div>')
        return (f'<div class="ctr sub case-ev"><div class="ctr-h">⚖ case evidence · cider'
                f'<span class="ctr-n">{len(claims)}</span></div>'
                f'<div class="ctr-body">{chips}</div></div>')

    # Group by context (outer container) › theme/people (inner container).
    by_ctx: dict[str, list] = {}
    for n in nodes:
        by_ctx.setdefault(n["ctx"] or "other", []).append(n)
    ctx_keys = ([c for c in _CTX_ORDER if c in by_ctx]
                + [c for c in by_ctx if c not in _CTX_ORDER])

    outer = []
    for c in ctx_keys:
        subs: dict[str, list] = {}
        for n in by_ctx[c]:
            sk = "people" if n["kind"] == "person" else (n["theme"] or "notes")
            subs.setdefault(sk, []).append(n)
        # people/themed sub-containers first, loose "notes" last
        sub_keys = sorted(subs, key=lambda k: (k in ("notes",), k != "people", k))
        sub_html = []
        for sk in sub_keys:
            chips = "".join(
                f'<div class="fitem k-{_esc(n["kind"])}" data-tags="{tags(n)}" '
                f'style="--c:{_CTX_COLOR.get(c, "#64748B")}" title="{_esc(n["title"])}">'
                f'{_esc(n["title"][:38])}</div>' for n in subs[sk])
            sub_html.append(
                f'<div class="ctr sub"><div class="ctr-h">{_esc(sk)}'
                f'<span class="ctr-n">{len(subs[sk])}</span></div>'
                f'<div class="ctr-body">{chips}</div></div>')
        if c == "case":                                    # attach the gated evidence sub-container
            sub_html.append(_claim_sub())
        outer.append(
            f'<div class="ctr" data-ctx="{_esc(c)}" style="--c:{_CTX_COLOR.get(c, "#64748B")}">'
            f'<div class="ctr-h ctr-top">{_esc(c)}</div>'
            f'<div class="ctr-body">{"".join(sub_html)}</div></div>')

    return (
        '<div id="field" class="field nest" hidden>'
        '<div class="field-ctl">connected containers · <b>click an item to trace its links</b>'
        '<span class="field-hint">bounded &amp; nested, wired across contexts — Nelson / '
        'Tinderbox</span></div>'
        f'<div class="nest-plane"><svg class="nest-links"></svg>{"".join(outer)}</div></div>')


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


# Context → a calm pill colour (life-domain lens; legal/case reads warm, the rest cool/muted).
_CTX_COLOR = {
    "legal": "#B45309", "local-authority": "#7C3AED", "medical": "#059669",
    "consulting": "#0E7490", "work": "#2563EB", "personal": "#64748B",
}
_INBOX_CACHE = Path(__file__).resolve().parent / "data" / "inbox_cache.json"


def _inbox_card() -> str:
    """Unified inbox — mail (both accounts) + iMessage in one stream, faceted by venue & context.

    Venue = where it arrived (account/channel); context = the derived life-domain (personal /
    consulting / legal / local-authority / medical / work). Two independent filter rows let Adam
    pivot either way — e.g. 'legal' to see every case message across venues at once.
    """
    try:
        data = json.loads(_INBOX_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _card("inbox", "Inbox", "",
                     '<p class="empty sm">No inbox snapshot yet — hit <b>refresh</b> or run '
                     '<code>python3 lib/inbox.py --cache</code>.</p>', collapsed=True)
    items = data.get("items", [])
    if not items:
        return _card("inbox", "Inbox", "", '<p class="empty sm">Inbox clear. 🎉</p>',
                     collapsed=True)
    facets = data.get("facets", {})

    def chips(dim: str, key: str) -> str:
        counts = facets.get(dim, {})
        btns = [f'<button class="ichip on" data-{key}="all">all</button>']
        for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            dot = (f'<i class="cdot" style="background:{_CTX_COLOR.get(name, "#64748B")}"></i>'
                   if dim == "context" else "")
            btns.append(f'<button class="ichip" data-{key}="{_esc(name)}">'
                        f'{dot}{_esc(name)} <b>{n}</b></button>')
        return f'<div class="ifac" data-dim="{dim}">' + "".join(btns) + "</div>"

    rows = []
    for m in items:
        col = _CTX_COLOR.get(m["context"], "#64748B")
        unread = ' data-unread="1"' if m.get("unread") else ""
        mkey = m.get("key", "")
        pin = _pin_btn("message", mkey, _is_pinned("message", mkey)) if mkey else ""
        rows.append(
            f'<li class="row irow" data-venue="{_esc(m["venue"])}" '
            f'data-context="{_esc(m["context"])}"{unread}>'
            f'<span class="when">{_esc(m.get("date") or "")}</span>'
            f'<span class="what"><span class="ivenue">{_esc(m["venue"])}</span> '
            f'<span class="ictx" style="color:{col}">{_esc(m["context"])}</span> '
            f'<b>{_esc(m["who"])}</b> — {_esc(m["subject"])}</span>{pin}</li>')
    at = _esc(data.get("at") or "")
    body = (chips("venue", "v") + chips("context", "c")
            + f'<ul class="rows inbox-rows">{"".join(rows)}</ul>'
            + (f'<div class="sum-at">as of {at}</div>' if at else "")
            + _INBOX_JS)
    return _card("inbox", "Inbox", str(len(items)), body, collapsed=True)


# Filter script: one active venue + one active context; a row shows only if it matches both.
_INBOX_JS = """<script>(function(){
  var card=document.currentScript.closest('.card'); if(!card) return;
  var sel={venue:'all',context:'all'};
  function apply(){
    card.querySelectorAll('.irow').forEach(function(r){
      var okV=sel.venue==='all'||r.dataset.venue===sel.venue;
      var okC=sel.context==='all'||r.dataset.context===sel.context;
      r.style.display=(okV&&okC)?'':'none';
    });
  }
  card.querySelectorAll('.ifac').forEach(function(f){
    var dim=f.dataset.dim;
    f.querySelectorAll('.ichip').forEach(function(b){
      b.addEventListener('click',function(e){
        e.stopPropagation();
        f.querySelectorAll('.ichip').forEach(function(x){x.classList.remove('on');});
        b.classList.add('on');
        sel[dim]=b.dataset.v||b.dataset.c; apply();
      });
    });
  });
})();</script>"""


def _reminders_card() -> str:
    """Apple Reminders — open items mirrored from Siri / the Reminders app / the WhatsApp agent.

    This is the phone-capture surface: anything you tell Siri, add in the Reminders app, or send
    the WhatsApp assistant lands here. The PA reads it (read-only) so it shows up in one view.
    """
    try:
        data = json.loads(_REMIND_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if not data:
        body = ('<p class="empty sm">No reminders snapshot yet — the monitor refreshes this, '
                'or run <code>python3 lib/reminders.py</code>.</p>')
        return _card("reminders", "Reminders", "", body, collapsed=True)
    if not data.get("ok"):
        note = data.get("note") or "Reminders not readable."
        return _card("reminders", "Reminders", "", f'<p class="empty sm">{_esc(note)}</p>',
                     collapsed=True)
    items = data.get("items", [])
    if not items:
        return _card("reminders", "Reminders", "",
                     '<p class="empty sm">No open reminders. 🎉</p>', collapsed=True)
    rows = "".join(
        f'<li class="row"><span class="when">{_esc(it["due"][:10]) if it.get("due") else "—"}</span>'
        f'<span class="what">{_esc(it["title"])}</span></li>' for it in items)
    at = _esc(data.get("at") or "")
    body = f'<ul class="rows">{rows}</ul>' + (f'<div class="sum-at">as of {at}</div>' if at else "")
    return _card("reminders", "Reminders", str(len(items)), body, collapsed=True)


def _person_controls(p: dict) -> tuple[str, str]:
    """(kind-toggle badge, priority chip) forms for a person row."""
    is_org = p["kind"] == "org"
    badge = "🏢" if is_org else "👤"
    other = "person" if is_org else "org"
    kind_toggle = (
        f'<form class="pkind" method="post" action="/person-kind">'
        f'<input type="hidden" name="id" value="{p["id"]}">'
        f'<input type="hidden" name="kind" value="{other}">'
        f'<button title="typed as {p["kind"]} — click to mark as {other}">{badge}</button></form>')
    prio = p["priority"]
    prio_chip = (
        f'<form class="pprio p-{_esc(prio)}" method="post" action="/person-priority">'
        f'<input type="hidden" name="id" value="{p["id"]}">'
        f'<button title="priority {prio} — click to cycle">{_esc(prio)}</button></form>')
    return kind_toggle, prio_chip


def _person_edit_form(p: dict) -> str:
    """Inline edit form so Adam can correct any machine-guessed metadata on a person."""
    return (
        '<form class="edit" method="post" action="/person-edit" hidden>'
        f'<input type="hidden" name="id" value="{p["id"]}">'
        f'<input name="name" value="{_esc(p["name"])}" title="name">'
        f'{_sel("kind", ["person", "org"], p.get("kind") or "person")}'
        f'{_sel("circle", list(CIRCLES), p.get("circle") or "peripheral")}'
        f'{_sel("priority", ["low", "normal", "high"], p.get("priority") or "normal")}'
        f'<input name="context" value="{_esc(p.get("context") or "")}" placeholder="context">'
        f'<input name="birthday" value="{_esc(p.get("birthday") or "")}" placeholder="birthday MM-DD">'
        f'<input name="relationship" value="{_esc(p.get("relationship") or "")}" '
        'placeholder="relationship">'
        f'<input name="notes" value="{_esc(p.get("notes") or "")}" placeholder="notes">'
        '<button>save</button></form>')


def _person_row(p: dict) -> str:
    kind_toggle, prio_chip = _person_controls(p)
    reason = p.get("_reason") or ""
    reason_html = (f'<span class="preason">{_esc(reason)}</span>'
                   if reason and reason not in (p["priority"], p.get("circle")) else "")
    return (
        f'<li class="row prow" data-person="{_esc(p["name"])}" data-kind="{p["kind"]}" '
        f'role="button" tabindex="0">{kind_toggle}'
        f'<span class="what">{_esc(p["name"])} {reason_html}</span>'
        f'{prio_chip}{_pin_btn("person", p["name"], p["_pinned"])}'
        f'<button type="button" class="edit-btn" title="edit">✎</button>'
        f'{_person_edit_form(p)}</li>')


def _people_card() -> str:
    """People grouped by CIRCLE OF PROXIMITY (inner→peripheral), typed (person/org), each editable.

    Circle is a relational-distance classifier auto-guessed from interaction volume and then
    corrected by hand (the ✎ edit form fixes name/kind/circle/priority/context/birthday/notes).
    Within each circle, rows sit in deserving-attention order; closer circles also lift attention.
    """
    total = len(load_people())
    btn = ('<form class="sum-btn" method="post" action="/sync-people">'
           '<button title="refresh people from your mail contacts">↻ sync from mail</button></form>')
    if not total:
        body = (btn + '<p class="empty sm">No people yet — <b>sync from mail</b> to populate '
                'from who actually emails you. (Full Monica CRM optional — MONICA_SETUP.md.)</p>')
        return _card("people", "People", "", body, collapsed=True)
    ranked = ranked_people(set(_PINS.get("person", [])))
    by_circle: dict[str, list] = {c: [] for c in CIRCLES}
    for p in ranked:
        by_circle.get(p.get("circle") or "peripheral", by_circle["peripheral"]).append(p)
    blocks = [btn]
    for circle in CIRCLES:
        grp = by_circle[circle]
        if not grp:
            continue
        rows = "".join(_person_row(p) for p in grp)
        # inner circle open by default; the long tail (wider/peripheral) folded until wanted.
        blocks.append(_details(f"people-circle-{circle}", circle,
                               f'<ul class="rows">{rows}</ul>', count=len(grp),
                               open_default=circle in ("inner", "close")))
    return _card("people", "People", str(total), "".join(blocks), collapsed=True)


def _proposed_events_card() -> str:
    """Phase 2 — appointments the monitor detected in incoming messages, not yet on the calendar.

    Read-only surface for `data/proposed_events.json`. Creating the real event is confirm-required
    (Phase 3); for now Adam replies 'add' on Signal. Renders nothing when there are no proposals.
    """
    try:
        items = json.loads((repo_root() / "data" / "proposed_events.json")
                           .read_text(encoding="utf-8")).get("items", [])
    except (OSError, ValueError):
        return ""
    live = [e for e in items if (e.get("status") or "proposed") in ("proposed", "confirmed")]
    if not live:
        return ""
    rows = ""
    for e in reversed(live[-8:]):
        key, st = _esc(e.get("key", "")), (e.get("status") or "proposed")
        w = e.get("when") or {}
        if st == "confirmed":
            action = '<span class="ev-q">queued ✓</span>'
        else:
            action = (
                f'<form class="ev-add" method="post" action="/event-add">'
                f'<input type="hidden" name="key" value="{key}">'
                f'<button title="add to your fairres calendar">＋ add</button></form>'
                f'<form class="ev-dismiss" method="post" action="/event-dismiss">'
                f'<input type="hidden" name="key" value="{key}">'
                f'<button title="dismiss — not a real appointment">✕</button></form>')
        rows += (f'<li class="row prow"><span class="when">{_esc(w.get("display", ""))}</span>'
                 f'<span class="what">📅 {_esc((e.get("snippet") or "")[:50])} '
                 f'<span class="preason">{_esc(e.get("sender") or "")}</span></span>{action}</li>')
    body = (f'<ul class="rows">{rows}</ul>'
            '<p class="empty sm">Detected in your messages, not on your calendar. '
            '<b>＋ add</b> queues it for <b>fairresconman</b> (created at your next check-in / on '
            'request).</p>')
    return _card("proposed", "📅 Proposed appointments", str(len(live)), body)


def _priorities_card(today: date) -> str:
    """The main view: everything Adam has explicitly pinned — tasks, people, messages — together.

    Explicit prioritisation that overrides derived urgency: whatever he stars lands here, at the
    top, uncollapsed. Empty until he pins something, with a one-line hint on how.
    """
    pins = _PINS
    blocks = []

    pinned_tasks = [t for t in load_tasks()
                    if not t.get("completed") and str(t["id"]) in pins["task"]]
    if pinned_tasks:
        rows = "".join(
            f'<li class="row"><span class="what">◇ {_esc(t["title"])}'
            + (f' <span class="due due-{_due_state(t.get("due_date"), today)}">'
               f'{_esc(t["due_date"])}</span>' if t.get("due_date") else "")
            + f'</span>{_pin_btn("task", t["id"], True)}</li>' for t in pinned_tasks)
        blocks.append(f'<div class="sub">tasks</div><ul class="rows">{rows}</ul>')

    if pins["person"]:
        rows = "".join(
            f'<li class="row person" data-person="{_esc(name)}" role="button" tabindex="0">'
            f'<span class="what">◈ {_esc(name)}</span>'
            f'{_pin_btn("person", name, True)}</li>' for name in pins["person"])
        blocks.append(f'<div class="sub">people</div><ul class="rows">{rows}</ul>')

    if pins["message"]:
        try:
            msgs = {m.get("key"): m for m in
                    json.loads(_INBOX_CACHE.read_text(encoding="utf-8")).get("items", [])}
        except (OSError, ValueError):
            msgs = {}
        rows = ""
        for k in pins["message"]:
            m = msgs.get(k)
            if not m:
                continue
            col = _CTX_COLOR.get(m["context"], "#64748B")
            rows += (f'<li class="row"><span class="what">✉ '
                     f'<span class="ictx" style="color:{col}">{_esc(m["context"])}</span> '
                     f'<b>{_esc(m["who"])}</b> — {_esc(m["subject"])}</span>'
                     f'{_pin_btn("message", k, True)}</li>')
        if rows:
            blocks.append(f'<div class="sub">messages</div><ul class="rows">{rows}</ul>')

    n = sum(len(pins[k]) for k in pins)
    if not blocks:
        body = ('<p class="empty sm">Nothing pinned yet. Tap the ☆ on any task, person, or '
                'message to prioritise it here — your hand-picked main view.</p>')
        return _card("priorities", "Priorities", "", body)
    return _card("priorities", "Priorities", str(n), "".join(blocks))


def _brief_hero() -> str:
    """The situational companion brief — the primary surface, above the global view.

    A warm, attention-ranked orientation ('where you are, the moves that matter most') from
    lib/brief (claude, cached). This reframes the page from a tracking panel you audit into an
    assistant that keeps you oriented; the cards below remain as the global 'see everything' layer.
    """
    b = load_brief()
    if not b or not b.get("brief"):
        return ('<section class="brief brief-empty">'
                '<p>Your brief will appear here. Hit <b>↻ refresh</b> to generate it.</p>'
                '</section>')
    moves = "".join(f'<li>{_esc(m)}</li>' for m in (b.get("moves") or []))
    moves_html = f'<ul class="moves">{moves}</ul>' if moves else ""
    at = _esc(b.get("at") or "")
    return (
        '<section class="brief">'
        f'<p class="brief-text">{_esc(b["brief"])}</p>'
        + (f'<div class="moves-wrap"><span class="moves-lbl">next moves</span>{moves_html}</div>'
           if moves_html else "")
        + f'<div class="brief-at">as of {at}</div>'
        '</section>'
    )


def _time_energy_strip(today: date, events_by_acct: dict) -> str:
    """Time-awareness + 'right now' energy/time matching (ADHD: make time visible, cut decisions).

    Left: a live clock, a day-progress bar (08:00→20:00), and a countdown to the next meeting —
    time you can *see*, not calculate (the time-blindness aid). Right: 'right now I have [time] /
    [energy]' chips that dim tasks down to the quick wins that fit — externalising the "what can I
    actually do now?" decision. Both are client-side (see _TIME_JS); today's timed events ride
    along in a JSON script tag so the countdown stays live between rebuilds.
    """
    tstr = today.isoformat()
    seen, timed = set(), []
    for acct in ACCOUNTS:
        for e in events_by_acct.get(acct["id"], []):
            if e.get("date") == tstr and e.get("when") and e["when"] != "all day":
                k = (e["when"], e["title"])
                if k not in seen:
                    seen.add(k)
                    timed.append({"t": e["when"], "title": (e["title"] or "")[:40]})
    timed.sort(key=lambda x: x["t"])
    # JSON in a <script> — escape '<' so a title can't break out of the tag.
    ev_json = json.dumps(timed).replace("<", "\\u003c")
    return (
        '<div class="tstrip">'
        '<div class="nownext">'
        '<span class="clock" id="clock">—</span>'
        '<div class="dayprog"><i id="dayfill"></i></div>'
        '<span class="nextev" id="nextev"></span>'
        '</div>'
        '<div class="rightnow">'
        '<span class="rn-lbl">right now:</span>'
        '<span class="rn-grp rn-time">'
        '<button class="rn on" data-min="0">any time</button>'
        '<button class="rn" data-min="15">≤15m</button>'
        '<button class="rn" data-min="30">≤30m</button>'
        '<button class="rn" data-min="60">≤1h</button></span>'
        '<span class="rn-grp rn-energy">'
        '<button class="re on" data-energy="any">any energy</button>'
        '<button class="re" data-energy="low">low</button>'
        '<button class="re" data-energy="medium">med</button>'
        '<button class="re" data-energy="high">high</button></span>'
        '<span class="rn-count" id="rncount"></span>'
        '</div>'
        f'<script type="application/json" id="today-events">{ev_json}</script>'
        '</div>'
    )


def _render_html(today: date) -> str:
    global _PINS
    _PINS = load_pins()
    tasks = load_tasks()
    open_tasks = [t for t in tasks if not t.get("completed")]
    done_tasks = [t for t in tasks if t.get("completed")]
    due_today = sum(1 for t in open_tasks
                    if _due_state(t.get("due_date"), today) == "today")
    overdue = sum(1 for t in open_tasks
                  if _due_state(t.get("due_date"), today) == "overdue")

    # Mail + calendar come from the pre-computed glance cache (lib/glance.refresh), NOT live —
    # so this render (which runs on every mutation) stays instant. Refreshed by monitor/​/refresh.
    glance = glance_load()
    worth_by_acct = {a["id"]: (glance["mail"].get(a["id"], {}).get("worth", []),
                               glance["mail"].get(a["id"], {}).get("noise", 0))
                     for a in ACCOUNTS}
    new_mail = sum(len(w) for w, _ in worth_by_acct.values())
    events_by_acct = glance.get("events", {})

    # Next meeting across both calendars over the next 2 days (from the cache).
    next_mtg = "—"
    upcoming = []
    for acct in ACCOUNTS:
        for e in events_by_acct.get(acct["id"], []):
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
    cards = (_priorities_card(today) + _proposed_events_card()
             + _today_card(today, events_by_acct)
             + _tasks_card(today, open_tasks)
             + _messages_card(worth_by_acct) + _inbox_card() + _work_card()
             + _reminders_card() + _people_card() + _activity_card())

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
        '<button id="field-btn" title="the Nest — bounded, nested containers wired by '
        'connections (Nelson / Tinderbox)">✳ nest</button>'
        '<button id="case-btn" title="reveal the gated case-evidence layer in the Nest '
        '(cider-store claim graph — private)">⚖ case</button>'
        '<button id="theme-btn" title="cycle theme">◐ theme</button>'
        '<button id="fs-dn" title="smaller text">A−</button>'
        '<button id="fs-up" title="larger text">A+</button></div></header>'
        # Companion brief leads (situational, attention-ranked); the deck + cards are the
        # global 'see everything' layer beneath it.
        f'{_brief_hero()}'
        f'{_time_energy_strip(today, events_by_acct)}'
        f'<div class="deck">{deck}</div>'
        # Two refresh affordances: rebuild the page from current data, or pull the work tabs.
        '<div class="ctl">'
        '<form method="post" action="/refresh"><button class="ghost" title="rebuild now">'
        '↻ refresh</button></form>'
        '<form method="post" action="/pull-work" class="pull">'
        '<button class="ghost" title="read the Enact work tabs (needs the Enact Chrome)">'
        'pull work</button></form>'
        '<form method="post" action="/push-reminders" class="pushrem">'
        '<button class="ghost" title="push open tasks to the PA Tasks list in Apple Reminders '
        '(phone / Watch / Siri)">↗ Reminders</button></form>'
        '</div>'
        '<form class="capture" method="post" action="/capture">'
        '<input name="title" placeholder="Add a task…" autocomplete="off" autofocus>'
        '<input name="theme" placeholder="theme" autocomplete="off" class="theme">'
        '<select name="energy"><option value="low">low</option>'
        '<option value="medium" selected>med</option><option value="high">high</option></select>'
        '<select name="priority"><option value="high">high</option>'
        '<option value="normal" selected>normal</option><option value="low">low</option></select>'
        '<button>Add</button>'
        '</form>'
        f'{facet_bar}'
        '<div id="thread" class="thread" hidden></div>'
        f'<div class="grid">{cards}</div>'
        f'{_field_view(today)}'
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
/* Collapsible groups (<details>) — each category / band / circle folds on its own. */
.grp{ margin:.15rem 0; }
summary.sub.grp-h{ display:flex; align-items:center; gap:.35rem; cursor:pointer;
  list-style:none; margin:.5rem 0 .25rem; padding:.15rem 0; user-select:none; }
summary.sub.grp-h::-webkit-details-marker{ display:none; }
summary.sub.grp-h::marker{ content:""; }
summary.sub.grp-h:hover{ color:var(--fg); }
.grp-n{ margin-left:.1rem; opacity:.6; font-variant-numeric:tabular-nums;
  background:var(--bg); border:1px solid var(--line); border-radius:999px; padding:0 .38rem; }
.grp-chev{ margin-left:auto; font-size:.62rem; color:var(--muted);
  transform:rotate(-90deg); transition:transform .15s; }
details.grp[open]>summary .grp-chev{ transform:rotate(0); }
details.grp:not([open])>summary.sub{ color:var(--muted); opacity:.85; }
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
/* Unified inbox: venue + context filter chips and message rows */
.ifac{ display:flex; flex-wrap:wrap; gap:.28rem; margin:.15rem 0 .4rem; }
.ichip{ font:.66rem/1 var(--mono); letter-spacing:.02em; padding:.24rem .5rem; cursor:pointer;
  border:1px solid var(--line); border-radius:1rem; background:transparent; color:var(--muted);
  display:inline-flex; align-items:center; gap:.3rem; }
.ichip:hover{ color:var(--fg); }
.ichip.on{ background:var(--accent-soft,#e8f0ee); color:var(--fg); border-color:var(--accent,#2b7a6f); }
.ichip b{ opacity:.65; font-weight:600; }
.cdot{ width:.5rem; height:.5rem; border-radius:50%; display:inline-block; }
.irow .ivenue{ font:.6rem/1 var(--mono); text-transform:uppercase; letter-spacing:.05em;
  color:var(--muted); border:1px solid var(--line); border-radius:.3rem; padding:.05rem .28rem; }
.irow .ictx{ font:.62rem/1 var(--mono); text-transform:uppercase; letter-spacing:.04em; }
.irow[data-unread="1"] b{ color:var(--fg); }
.inbox-rows{ max-height:22rem; overflow-y:auto; }
/* Explicit prioritisation: ★ pin toggle + the Priorities main-view card */
.pin{ display:inline-flex; margin:0; }
.pin button{ background:none; border:none; cursor:pointer; color:var(--muted);
  font-size:.95rem; line-height:1; padding:0 .18rem; opacity:.55; }
.pin button:hover{ opacity:1; color:#E0A500; }
.pin.on button{ color:#E0A500; opacity:1; }
.pchip-wrap{ display:inline-flex; align-items:center; gap:.05rem; }
.irow .pin, .row .pin{ flex:0 0 auto; margin-left:auto; }
.card[data-key=priorities]{ border-color:#E0A500; }
.card[data-key=priorities] .ttl{ color:#B8860B; }
.card[data-key=priorities] .cnt{ background:#E0A500; color:#3a2c00; }
/* Situational companion brief — the hero surface */
.brief{ margin:.4rem 0 .2rem; padding:1rem 1.15rem; border-radius:.7rem;
  background:linear-gradient(180deg, var(--accent-soft,#eaf3f1), var(--card));
  border:1px solid var(--line); }
.brief-text{ font:400 1.12rem/1.55 var(--sans, inherit); color:var(--fg); margin:0;
  max-width:60ch; }
.moves-wrap{ margin-top:.7rem; display:flex; align-items:baseline; gap:.6rem; flex-wrap:wrap; }
.moves-lbl{ font:.66rem/1 var(--mono); text-transform:uppercase; letter-spacing:.08em;
  color:var(--muted); }
.moves{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:.28rem; }
.moves li{ font:500 .96rem/1.4 var(--sans, inherit); color:var(--fg); padding-left:1.1rem;
  position:relative; }
.moves li:before{ content:"→"; position:absolute; left:0; color:var(--accent,#2b7a6f); font-weight:600; }
.brief-at{ margin-top:.55rem; font:.66rem/1 var(--mono); color:var(--muted); }
.brief-empty p{ margin:0; color:var(--muted); font-size:.92rem; }
/* Time-awareness + right-now strip */
.tstrip{ display:flex; flex-wrap:wrap; align-items:center; gap:.5rem 1.1rem; margin:.5rem 0;
  padding:.5rem .7rem; border:1px solid var(--line); border-radius:.6rem; background:var(--card); }
.nownext{ display:flex; align-items:center; gap:.6rem; min-width:0; }
.clock{ font:600 1.05rem/1 var(--mono); color:var(--fg); letter-spacing:.02em; }
.dayprog{ position:relative; width:8rem; height:.42rem; border-radius:1rem;
  background:var(--line); overflow:hidden; }
.dayprog i{ position:absolute; inset:0 auto 0 0; width:0; background:var(--accent,#2b7a6f);
  border-radius:1rem; transition:width .6s ease; }
.nextev{ font:.78rem/1.3 var(--mono); color:var(--muted); }
.nextev.soon{ color:#B45309; font-weight:600; }
.rightnow{ display:flex; flex-wrap:wrap; align-items:center; gap:.3rem .5rem; }
.rn-lbl{ font:.7rem/1 var(--mono); color:var(--muted); text-transform:uppercase; letter-spacing:.05em; }
.rn-grp{ display:inline-flex; gap:.22rem; }
.rn, .re{ font:.68rem/1 var(--mono); padding:.24rem .5rem; cursor:pointer; border-radius:1rem;
  border:1px solid var(--line); background:transparent; color:var(--muted); }
.rn:hover, .re:hover{ color:var(--fg); }
.rn.on, .re.on{ background:var(--accent-soft,#e8f0ee); color:var(--fg); border-color:var(--accent,#2b7a6f); }
.rn-count{ font:.72rem/1 var(--mono); color:var(--accent,#2b7a6f); font-weight:600; }
.task.rn-dim{ opacity:.28; filter:grayscale(.4); }
/* People rows: kind toggle, priority chip, attention reason */
.prow{ align-items:center; flex-wrap:wrap; }
.prow .edit{ flex:1 1 100%; }
.prow .edit input[name=name]{ flex:1 1 8rem; }
.pkind{ display:inline-flex; margin:0 .35rem 0 0; flex:0 0 auto; }
.pkind button{ background:none; border:none; cursor:pointer; font-size:.92rem; padding:0;
  line-height:1; opacity:.9; }
.preason{ font:.66rem/1 var(--mono); color:var(--muted); margin-left:.35rem; }
.pprio{ display:inline-flex; margin:0 .3rem 0 auto; flex:0 0 auto; }
.pprio button{ font:.6rem/1 var(--mono); text-transform:uppercase; letter-spacing:.04em;
  padding:.16rem .4rem; border-radius:1rem; cursor:pointer; border:1px solid var(--line);
  background:transparent; color:var(--muted); }
.pprio.p-high button{ color:#B45309; border-color:#B45309; font-weight:700; }
.pprio.p-low button{ opacity:.6; }
/* Proposed-appointment add/dismiss */
.ev-add,.ev-dismiss{ display:inline-flex; margin-left:.3rem; flex:0 0 auto; }
.ev-add button{ font:.62rem/1 var(--mono); padding:.14rem .45rem; border-radius:1rem; cursor:pointer;
  border:1px solid var(--accent,#2b7a6f); color:var(--accent,#2b7a6f); background:transparent;
  font-weight:650; }
.ev-dismiss button{ font:.62rem/1 var(--mono); padding:.14rem .4rem; border-radius:1rem;
  cursor:pointer; border:1px solid var(--line); color:var(--muted); background:transparent; }
.ev-q{ margin-left:.3rem; font:.62rem/1 var(--mono); color:var(--accent,#2b7a6f); }
/* The Nest — bounded, nested containers wired by connections (Nelson / Tinderbox) */
body.fieldmode .grid, body.fieldmode .brief, body.fieldmode .tstrip,
body.fieldmode .deck, body.fieldmode .ctl, body.fieldmode .capture,
body.fieldmode .facets, body.fieldmode #thread{ display:none; }
.field{ margin:.5rem 0; }
.field-ctl{ display:flex; align-items:center; gap:.5rem; flex-wrap:wrap;
  font:.8rem/1 var(--mono); color:var(--muted); margin-bottom:.5rem; }
.field-hint{ margin-left:auto; opacity:.75; }
.nest-plane{ position:relative; display:flex; flex-wrap:wrap; align-items:flex-start;
  gap:.9rem; }
.nest-links{ position:absolute; inset:0; z-index:5; pointer-events:none; overflow:visible; }
.nlink{ fill:none; stroke:var(--accent,#2b7a6f); stroke-width:1.6; opacity:.7;
  stroke-linecap:round; }
/* Containers: bounded, titled, nestable. Outer = context (colour-keyed), inner = theme/people. */
.ctr{ border:1px solid var(--line); border-radius:.6rem; background:var(--card);
  flex:1 1 20rem; min-width:16rem; overflow:hidden; }
.ctr[data-ctx]{ border-top:3px solid var(--c,#64748B); flex:1 1 22rem; }
.ctr-h{ font:.66rem/1 var(--mono); letter-spacing:.05em; text-transform:uppercase;
  color:var(--muted); padding:.42rem .6rem; display:flex; align-items:center; gap:.4rem;
  border-bottom:1px solid var(--line); background:color-mix(in srgb, var(--c,#64748B) 7%, var(--card)); }
.ctr-top{ color:var(--c,#334155); font-weight:700; font-size:.72rem; }
.ctr-n{ margin-left:auto; opacity:.65; }
.ctr-body{ padding:.5rem; display:flex; flex-wrap:wrap; gap:.55rem; align-content:flex-start; }
.ctr.sub{ flex:1 1 13rem; min-width:11rem; background:transparent; }
.ctr.sub>.ctr-body{ padding:.4rem; }
/* Items: readable chips held inside their container. */
.fitem{ font:.74rem/1.25 var(--sans, inherit); color:var(--fg); cursor:pointer; position:relative;
  padding:.26rem .5rem; border-radius:.4rem; border:1px solid var(--line);
  background:var(--bg); border-left:3px solid var(--c,#64748B); max-width:100%;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; transition:opacity .15s,box-shadow .15s; }
.fitem.k-person{ border-radius:1rem; font-weight:600; }
.fitem:hover{ box-shadow:0 1px 6px rgba(0,0,0,.12); overflow:visible; z-index:7; }
.fitem.lit{ z-index:6; }
.fitem.focus{ box-shadow:0 0 0 2px var(--c,#2b7a6f); font-weight:650; }
.fitem.dim{ opacity:.28; }
/* Gated case-evidence layer — off unless ⚖ case is on. Adam's private view only. */
.case-ev{ display:none; }
body.casemode .case-ev{ display:block; }
.case-ev>.ctr-h{ color:#B45309; border-color:#B45309;
  background:color-mix(in srgb, #B45309 8%, var(--card)); }
.fitem.k-claim{ border-left-color:#B45309; background:color-mix(in srgb,#B45309 5%,var(--bg));
  white-space:normal; max-width:16rem; }
.fitem.k-claim.st-contradicted, .fitem.k-claim.st-unsubstantiated,
.fitem.k-claim.st-unfounded{ border-left-color:#15803D; }
.fitem.k-claim.st-pending, .fitem.k-claim.st-disputed{ border-left-color:#B45309; }
#case-btn.on{ color:#B45309; border-color:#B45309; font-weight:650; }
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
  // ✎ edit: toggle the inline edit form for a task or a person row.
  document.querySelectorAll('.edit-btn').forEach(function(b){
    b.addEventListener('click', function(e){
      e.stopPropagation();
      var host=b.closest('.task, .prow'); var f=host&&host.querySelector('.edit');
      if(f) f.hidden=!f.hidden;
    });
  });
  // ✨ Magic ToDo: break a task into steps (fixed sensible detail), show it's working.
  document.querySelectorAll('.mtd').forEach(function(f){
    f.addEventListener('submit', function(){
      var b=f.querySelector('button'); b.textContent='…'; b.disabled=true;
    });
  });
  // "pull work" is slow (drives the Enact Chrome) — show it's working and block double-posts.
  document.querySelectorAll('form.pull').forEach(function(f){
    f.addEventListener('submit', function(){
      var b=f.querySelector('button'); b.textContent='pulling…'; b.disabled=true;
    });
  });

  // ── Less-global interaction: update the DOM in place, don't full-reload/jump-to-top ──
  try{ if('scrollRestoration' in history) history.scrollRestoration='manual'; }catch(e){}
  // Restore scroll after any submit that DID reload (edit/breakdown/refresh/person-*).
  try{ var _sy=sessionStorage.getItem('pa-scroll');
    if(_sy){ sessionStorage.removeItem('pa-scroll'); requestAnimationFrame(function(){ window.scrollTo(0, parseInt(_sy,10)||0); }); }
  }catch(e){}
  window.addEventListener('beforeunload', function(){ try{ sessionStorage.setItem('pa-scroll', String(window.scrollY)); }catch(e){} });

  function ajaxPost(form){
    return fetch(form.action, {method:'POST', headers:{'X-PA-Ajax':'1'},
      body:new URLSearchParams(new FormData(form))});
  }
  function bumpStat(sel, d){ var el=document.querySelector(sel);
    if(el){ var n=parseInt(el.textContent,10); if(!isNaN(n)) el.textContent=Math.max(0,n+d); } }
  // Complete / delete a task → fade out and remove ALL its DOM copies (the card renders each
  // task twice: category grid + spatial-map band). No reload, scroll stays put.
  document.querySelectorAll('form.done, form.del').forEach(function(f){
    f.addEventListener('submit', function(e){
      e.preventDefault();
      var idInp=f.querySelector('input[name=id]'), id=idInp?idInp.value:null, lis=[];
      if(id){ document.querySelectorAll('.task').forEach(function(t){
        var i=t.querySelector('input[name=id]'); if(i && i.value===id) lis.push(t); }); }
      else { var c=f.closest('.task'); if(c) lis.push(c); }
      lis.forEach(function(li){ li.style.transition='opacity .22s ease, transform .22s ease';
        li.style.opacity='0'; li.style.transform='translateX(10px)'; });
      ajaxPost(f).then(function(){
        setTimeout(function(){ lis.forEach(function(li){ li.remove(); }); }, 210);
        bumpStat('.stat[data-act="filter:all"] .n', -1);
      }).catch(function(){ lis.forEach(function(li){ li.style.opacity=''; li.style.transform=''; }); });
    });
  });
  // Pin ★ toggle in place.
  document.querySelectorAll('form.pin').forEach(function(f){
    f.addEventListener('submit', function(e){ e.preventDefault();
      ajaxPost(f).then(function(){ f.classList.toggle('on');
        var b=f.querySelector('button'); if(b) b.textContent=f.classList.contains('on')?'★':'☆'; });
    });
  });
  // Person priority chip cycles low→normal→high in place.
  document.querySelectorAll('form.pprio').forEach(function(f){
    f.addEventListener('submit', function(e){ e.preventDefault();
      ajaxPost(f).then(function(){
        var order=['low','normal','high'], cur='normal';
        ['low','normal','high'].forEach(function(p){ if(f.classList.contains('p-'+p)) cur=p; });
        var nxt=order[(order.indexOf(cur)+1)%3];
        f.classList.remove('p-low','p-normal','p-high'); f.classList.add('p-'+nxt);
        var b=f.querySelector('button'); if(b) b.textContent=nxt;
      });
    });
  });
  // Proposed appointment: dismiss removes the row; add marks it queued — both in place.
  document.querySelectorAll('form.ev-dismiss').forEach(function(f){
    f.addEventListener('submit', function(e){ e.preventDefault();
      var li=f.closest('.row');
      if(li){ li.style.transition='opacity .2s'; li.style.opacity='0'; }
      ajaxPost(f).then(function(){ if(li) setTimeout(function(){ li.remove(); }, 190); });
    });
  });
  document.querySelectorAll('form.ev-add').forEach(function(f){
    f.addEventListener('submit', function(e){ e.preventDefault();
      var li=f.closest('.row');
      ajaxPost(f).then(function(){
        if(li){ li.querySelectorAll('form.ev-add,form.ev-dismiss').forEach(function(x){x.remove();});
          var q=document.createElement('span'); q.className='ev-q'; q.textContent='queued ✓';
          li.appendChild(q); }
      });
    });
  });
  // Person kind toggle (👤 ↔ 🏢) in place.
  document.querySelectorAll('form.pkind').forEach(function(f){
    f.addEventListener('submit', function(e){ e.preventDefault();
      ajaxPost(f).then(function(){
        var inp=f.querySelector('input[name=kind]'), b=f.querySelector('button');
        var became=inp?inp.value:'person';
        if(b) b.textContent = became==='org' ? '🏢' : '👤';
        if(inp) inp.value = became==='org' ? 'person' : 'org';  // next click flips back
      });
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

  // ── The Nest: bounded nested containers, wired by traceable connections (Nelson-style) ──
  (function(){
    var field=document.getElementById('field'); if(!field) return;
    var fb=document.getElementById('field-btn');
    var plane=field.querySelector('.nest-plane');
    var svg=field.querySelector('.nest-links');
    var items=[].slice.call(field.querySelectorAll('.fitem'));
    function tagsOf(el){ return (el.dataset.tags||'').split('|').filter(Boolean); }
    function clear(){ while(svg.firstChild) svg.removeChild(svg.firstChild);
      items.forEach(function(m){ m.classList.remove('lit','dim','focus'); }); }
    function trace(el){
      clear();
      var mine=tagsOf(el); el.classList.add('lit','focus');
      var pr=plane.getBoundingClientRect();
      var W=plane.scrollWidth, H=plane.scrollHeight;
      svg.setAttribute('viewBox','0 0 '+W+' '+H);
      svg.style.width=W+'px'; svg.style.height=H+'px';
      var a=el.getBoundingClientRect();
      var ax=a.left-pr.left+a.width/2, ay=a.top-pr.top+a.height/2;
      items.forEach(function(m){
        if(m===el || m.offsetParent===null) return;   // skip self + gated/hidden (e.g. case-off)
        var shared=tagsOf(m).some(function(t){ return mine.indexOf(t)>=0; });
        if(shared){
          m.classList.add('lit');
          var b=m.getBoundingClientRect();
          var bx=b.left-pr.left+b.width/2, by=b.top-pr.top+b.height/2;
          var mx=(ax+bx)/2, my=(ay+by)/2-Math.min(90,Math.abs(bx-ax)*0.16);
          var p=document.createElementNS('http://www.w3.org/2000/svg','path');
          p.setAttribute('d','M'+ax+' '+ay+' Q'+mx+' '+my+' '+bx+' '+by);
          p.setAttribute('class','nlink'); svg.appendChild(p);
        } else { m.classList.add('dim'); }
      });
    }
    items.forEach(function(el){ el.addEventListener('click', function(e){
      e.stopPropagation();
      if(el.classList.contains('focus')){ clear(); return; }
      trace(el);
    });});
    plane.addEventListener('click', function(e){
      if(e.target===plane || e.target===svg || e.target.classList.contains('ctr-body')) clear(); });
    function show(on){ document.body.classList.toggle('fieldmode', on);
      field.hidden=!on; if(fb) fb.textContent=on?'▦ cards':'✳ nest';
      localStorage.setItem('pa-field', on?'1':'0');
      if(on && document.body.classList.contains('spatial')) setLayout(false);
      if(!on) clear(); }
    if(fb) fb.addEventListener('click', function(){ show(field.hidden); });
    if(localStorage.getItem('pa-field')==='1') show(true);   // survive the 60s auto-refresh
    // ⚖ case: reveal the gated case-evidence layer (off by default — the wall). Persisted.
    var cb=document.getElementById('case-btn');
    function caseMode(on){ document.body.classList.toggle('casemode', on);
      if(cb) cb.classList.toggle('on', on); localStorage.setItem('pa-case', on?'1':'0');
      clear(); if(on && field.hidden) show(true); }
    if(cb) cb.addEventListener('click', function(){
      caseMode(!document.body.classList.contains('casemode')); });
    if(localStorage.getItem('pa-case')==='1') caseMode(true);
  })();

  // Collapsible groups: restore each <details.grp>'s remembered open/closed state; persist on toggle.
  document.querySelectorAll('details.grp[data-grp]').forEach(function(d){
    var k='pa-grp-'+d.dataset.grp, saved=localStorage.getItem(k);
    if(saved==='1') d.open=true; else if(saved==='0') d.open=false;   // else keep server default
    d.addEventListener('toggle', function(){ localStorage.setItem(k, d.open?'1':'0'); });
  });

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
    var facetActive=(f&&f!=='all');
    document.querySelectorAll('.card[data-key="tasks"] details.grp').forEach(function(d){
      var vis=[].some.call(d.querySelectorAll('.task'),function(t){return t.style.display!=='none';});
      d.style.display=vis?'':'none';
      if(facetActive){ if(vis) d.open=true; }        // reveal matches even in a folded group
      else{ var s=localStorage.getItem('pa-grp-'+d.dataset.grp);   // cleared → restore choice
            if(s!==null) d.open=(s==='1'); }
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

  // ── Time awareness: live clock, day-progress bar (08:00–20:00), next-meeting countdown ──
  (function(){
    var box=document.getElementById('today-events');
    var clock=document.getElementById('clock'), nextev=document.getElementById('nextev'),
        fill=document.getElementById('dayfill');
    var evs=[]; if(box){ try{ evs=JSON.parse(box.textContent||'[]'); }catch(e){} }
    function toMin(s){ var p=(s||'0:0').split(':'); return (+p[0])*60+(+p[1]); }
    function tick(){
      var d=new Date(), nm=d.getHours()*60+d.getMinutes();
      if(clock) clock.textContent=String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');
      var frac=Math.max(0,Math.min(1,(nm-480)/(1200-480)));   // 08:00→20:00
      if(fill) fill.style.width=(frac*100).toFixed(1)+'%';
      if(nextev){
        var nx=null; for(var i=0;i<evs.length;i++){ if(toMin(evs[i].t)>nm){ nx=evs[i]; break; } }
        if(nx){ var g=toMin(nx.t)-nm, h=Math.floor(g/60), m=g%60;
          nextev.textContent='next: '+nx.title+' · in '+(h?h+'h ':'')+m+'m';
          nextev.classList.toggle('soon', g<=15);
        } else { nextev.textContent=evs.length?'nothing more scheduled today':'no meetings today'; }
      }
    }
    tick(); setInterval(tick, 20000);
  })();

  // ── "Right now I have [time]/[energy]" → dim tasks down to the quick wins that fit ──
  (function(){
    var minSel=0, enSel='any', rank={low:1,medium:2,high:3};
    function apply(){
      var idle=(minSel===0 && enSel==='any'), n=0;
      document.querySelectorAll('.task').forEach(function(t){
        var est=parseInt(t.dataset.est||'0',10), en=t.dataset.energy||'medium';
        var okT=(minSel===0)||(est>0? est<=minSel : true);   // no estimate = still eligible
        var okE=(enSel==='any')||(rank[en]<=rank[enSel]);     // low energy → only easy tasks
        var match=okT&&okE;
        t.classList.toggle('rn-dim', !idle && !match);
        if(match) n++;
      });
      var c=document.getElementById('rncount');
      if(c) c.textContent=idle?'':(n+' fit right now');
    }
    function wire(sel, on){ document.querySelectorAll(sel).forEach(function(b){
      b.addEventListener('click', function(){
        b.parentNode.querySelectorAll('button').forEach(function(x){x.classList.remove('on');});
        b.classList.add('on'); on(b); apply();
      }); }); }
    wire('.rn-time .rn', function(b){ minSel=parseInt(b.dataset.min,10); });
    wire('.rn-energy .re', function(b){ enSel=b.dataset.energy; });
  })();
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
