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
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.activity import unified  # noqa: E402
from lib.comms import ACCOUNTS, calendar_events, fetch_inbox, partition_inbox  # noqa: E402
from lib.mailsummary import load_summary  # noqa: E402
from lib.taskstore import CATEGORIES, load_tasks, repo_root  # noqa: E402

CATEGORY_COLOR = {
    "Work": "#2E75B6", "Personal": "#7C5CBF", "Health": "#3FA796",
    "Finance": "#C08A2E", "Other": "#7A8290",
}
_ACTIVITY_GLYPH = {"task": "◇", "calendar": "▣", "mail": "✉", "file": "▢"}


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
    body = "".join(blocks) or '<p class="empty">Nothing scheduled.</p>'
    return _card("today", "Today", str(total) if total else "", body)


def _tasks_card(today: date, open_tasks: list[dict]) -> str:
    groups = []
    for category in CATEGORIES:
        grp = [t for t in open_tasks if t.get("category") == category]
        if not grp:
            continue
        grp.sort(key=lambda x: (x.get("due_date") or "9999", x["id"]))
        rows = []
        for t in grp:
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
                steps_html = ('<ol class="steps">'
                              + "".join(f"<li>{_esc(s)}</li>" for s in steps) + "</ol>")
            edit_form = (
                f'<form class="edit" method="post" action="/edit" hidden>'
                f'<input type="hidden" name="id" value="{t["id"]}">'
                f'<input name="title" value="{_esc(t["title"])}">'
                f'{_sel("category", CATEGORIES, t.get("category"))}'
                f'<input name="theme" value="{_esc(t.get("theme") or "")}" placeholder="theme">'
                f'{_sel("priority", ["high", "normal", "low"], t.get("priority"))}'
                f'{_sel("energy", ["low", "medium", "high"], t.get("energy"))}'
                f'<input name="due" value="{_esc(t.get("due_date") or "")}" placeholder="due YYYY-MM-DD">'
                f'<button>Save</button></form>')
            rows.append(
                f'<li class="task" data-state="{st}" style="--accent:{accent}">'
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
                f'</div>{edit_form}{steps_html}</li>')
        groups.append(f'<div class="sub">{_esc(category)}</div>'
                      f'<ul class="tasks">{"".join(rows)}</ul>')
    body = "".join(groups) or '<p class="empty">Clear slate. ✨</p>'
    return _card("tasks", "Tasks", str(len(open_tasks)) if open_tasks else "", body)


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
        f'<li class="row"><span class="when">{_esc((a.timestamp or "")[:16])}</span>'
        f'<span class="what">{_ACTIVITY_GLYPH.get(a.source, "·")} {_esc(a.title[:56])}</span></li>'
        for a in stream[:16])
    return _card("activity", "Recent activity", "", f'<ul class="rows">{rows}</ul>',
                 collapsed=True)


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
             + _messages_card(worth_by_acct) + _activity_card())

    return (
        "<!doctype html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Personal Assistant</title>"
        f"<style>{_STYLE}</style></head><body><main>"
        f'<header class="top"><div class="date">{_esc(today.strftime("%A %-d %B %Y"))}'
        f'{wins}</div></header>'
        f'<div class="deck">{deck}</div>'
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
        f'<div class="grid">{cards}</div>'
        '<footer>Central overview · CIDER is your focus space · private</footer>'
        f"</main><script>{_SCRIPT}</script></body></html>"
    )


_STYLE = """
:root{ --bg:#f4f6f8; --card:#fff; --ink:#19212b; --muted:#6b7480; --line:#e4e8ec;
  --accent:#0f766e; --overdue:#b4472e; --today:#0f766e;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,monospace; }
@media (prefers-color-scheme:dark){ :root{ --bg:#0e1116; --card:#161b22; --ink:#e6e9ee;
  --muted:#8994a2; --line:#232a33; --accent:#2dd4bf; --overdue:#e8917a; --today:#2dd4bf; } }
*{ box-sizing:border-box; }
body{ margin:0; padding:1.4rem 1.1rem 3rem; background:var(--bg); color:var(--ink);
  font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
main{ max-width:1100px; margin:0 auto; }
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
.done{ margin:0; flex:0 0 auto; }
.done button{ cursor:pointer; width:1.7rem; height:1.7rem; border-radius:50%;
  border:1px solid var(--line); background:transparent; color:var(--muted); line-height:1; }
.done button:hover{ color:var(--accent); border-color:var(--accent); }
.empty{ color:var(--muted); font-size:.88rem; padding:.4rem 0; }
.empty.sm{ padding:.15rem 0; font-size:.82rem; }
footer{ color:var(--muted); font:.7rem/1 var(--mono); text-align:center; margin-top:1.5rem; }
@media (prefers-reduced-motion:reduce){ .chev{ transition:none; } }
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
        if(c){ c.classList.remove('collapsed'); c.scrollIntoView({behavior:'smooth',block:'start'}); }
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
  // Refresh every 60s so monitor updates appear — but never while adding a task.
  setInterval(function(){
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
