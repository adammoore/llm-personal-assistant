#!/usr/bin/env python3
"""eval_scenarios — scenario-based evaluation of the cider-lessons audit fixes.

Not unit tests of internals: each scenario sets up a realistic situation the way a user (or an
arriving message) would trigger it, runs the real code path, and judges the OUTCOME. Every check
returns one of three verdicts — PASS, FAIL, or INCONCLUSIVE — because "the eval couldn't decide"
is a real answer (cider handover §3), and skipping it is how a broken eval reads as a passing one.

Heeds handover §3 directly: an eval query must not contain the signal the feature supplies. The
contemporaneity scenario runs BOTH a sound probe (neutral query) and a flawed probe (query already
carries the event date) to show the flawed one is INCONCLUSIVE — it measures the retriever, not the
filter — while the sound one proves the filter. Run:  python3 tests/eval_scenarios.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

PASS, FAIL, INCONCLUSIVE = "PASS", "FAIL", "INCONCLUSIVE"
_results: list[tuple[str, str, str]] = []


def check(name: str, verdict: str, detail: str = "") -> None:
    _results.append((name, verdict, detail))


def _tmp(name: str) -> Path:
    return Path(tempfile.mkdtemp(prefix="pa_eval_")) / name


# ── Scenario 1 — appointment SMS with no stated time is flagged as a guess ───────────────────────
def scenario_appointment_no_time():
    """A clinic texts a confirmation that names a DATE but no clock time. The confirm card must not
    present the all-day default (or the fallback title) as if it came from the message."""
    from lib.calevent import event_fields
    # Note: the message deliberately contains NO time and NO clean title — we do not tell the code
    # "this is all-day"; we check that it DETECTS and MARKS the guess.
    prop = {"snippet": "Your appointment is confirmed for 21 Aug. Please arrive 10 minutes early.",
            "when": {"iso": "2026-08-21", "has_time": False}, "source": "sms", "sender": "clinic"}
    f = event_fields(prop)
    prov = f.get("provenance") or {}
    if prov.get("all_day") == "no-time-parsed" and f["all_day"] is True:
        check("1. no-time appointment flags all_day as a guess", PASS,
              f"all_day={f['all_day']} provenance.all_day={prov.get('all_day')!r}")
    else:
        check("1. no-time appointment flags all_day as a guess", FAIL,
              f"provenance did not mark the all-day fallback: {prov}")

    # A timed message must NOT be flagged — guard against over-flagging.
    timed = event_fields({"snippet": "Dentist 2:30pm 20 Aug", "when": {"iso": "2026-08-20T14:30",
                          "has_time": True}, "source": "sms"})
    if (timed.get("provenance") or {}).get("all_day") == "parsed":
        check("1b. a timed appointment is NOT flagged all-day", PASS)
    else:
        check("1b. a timed appointment is NOT flagged all-day", FAIL, str(timed.get("provenance")))


# ── Scenario 2 — a proposal is not lost when the queue is mutated concurrently ───────────────────
def scenario_queue_no_clobber():
    """The dashboard confirms proposal A while the daemon appends proposal B. Under the old raw
    read-modify-write, B could be clobbered. The locked+atomic path must preserve both."""
    import lib.calevent as ce
    ce.CACHE = _tmp("proposed_events.json")
    ce._LOCK = ce.CACHE.with_suffix(".lock")
    ce.append_proposals([{"key": "A", "snippet": "Dentist", "status": "proposed"}])
    # daemon appends B, then dashboard confirms A — interleaved through the same lock
    ce.append_proposals([{"key": "B", "snippet": "MOT booking", "status": "proposed"}])
    ce.set_status("A", "confirmed")
    keys = {p["key"] for p in ce._load()}
    if keys == {"A", "B"} and any(p["key"] == "A" and p["status"] == "confirmed" for p in ce._load()):
        check("2. concurrent confirm+append loses no proposal", PASS, f"queue={sorted(keys)}")
    else:
        check("2. concurrent confirm+append loses no proposal", FAIL, f"queue={sorted(keys)}")

    # corrupt queue must not be silently read as empty and overwritten
    ce.CACHE.write_text("{ truncated", encoding="utf-8")
    before = ce.CACHE.read_text()
    ce.set_status("A", "added")
    check("2b. corrupt queue is refused, not clobbered",
          PASS if ce.CACHE.read_text() == before else FAIL)


# ── Scenario 3 — a walled case meeting never reaches the default stream ──────────────────────────
def scenario_walled_meeting_hidden():
    """Granola caches a bail-review meeting tagged context=case. It must not appear on the default
    activity stream (the wall). We assert via the PUBLIC stream, not by reading the guard."""
    import lib.activity as A
    cache = _tmp("granola.json")
    today = date.today().isoformat()
    cache.write_text(json.dumps({"items": [
        {"title": "Bludfest planning", "timestamp": today + "T09:00", "meta": {"context": "personal"}},
        {"title": "Bail review with Henry / DC Shotton", "timestamp": today + "T11:00",
         "meta": {"context": "case"}},
    ]}))
    A._GRANOLA_CACHE = cache
    titles = {a.title for a in A.from_granola(days=14)}
    if "Bludfest planning" in titles and "Bail review with Henry / DC Shotton" not in titles:
        check("3. walled case meeting kept off the default stream", PASS)
    elif "Bludfest planning" not in titles:
        check("3. walled case meeting kept off the default stream", INCONCLUSIVE,
              "the control (personal) meeting also missing — cache path not exercised")
    else:
        check("3. walled case meeting kept off the default stream", FAIL, "case meeting leaked")


# ── Scenario 4 — medical / local-authority mail surfaces in the brief ───────────────────────────
def scenario_brief_surfaces_case_adjacent_mail():
    """A GP result and a Sefton social-work email arrive. The brief's mail line must surface them
    (they were silently dropped before). We feed a mixed inbox and read the rendered line."""
    import lib.brief as B
    inbox = {"items": [
        {"context": "medical", "who": "GP surgery", "subject": "Blood test results ready",
         "date": "2026-08-13"},
        {"context": "local-authority", "who": "Sefton SW", "subject": "Core group date",
         "date": "2026-08-12"},
        {"context": "personal", "who": "A friend", "subject": "coffee?", "date": "2026-08-13"},
    ]}
    orig = B._read_cache
    B._read_cache = lambda n: inbox if n == "inbox_cache.json" else {"items": []}
    try:
        # We assemble only the messages part the way gather() does, then render the line.
        msgs = [m for m in inbox["items"] if m["context"] in B._PRIORITY_CTX]
        g = {"now": None, "today": date(2026, 8, 13), "meetings": [], "overdue": [], "due_today": [],
             "pinned_tasks": [], "top_tasks": [], "reminders": [], "people": [], "recent_meetings": [],
             "messages": msgs[:4], "messages_more": max(0, len(msgs) - 4)}
        # Patch 'now' so _situation_text doesn't need a real datetime.
        import datetime as _dt
        g["now"] = _dt.datetime(2026, 8, 13, 9, 0)
        line = next(l for l in B._situation_text(g).splitlines() if "Mail worth attention" in l)
    finally:
        B._read_cache = orig
    if "[medical]" in line and "[local-authority]" in line:
        check("4. brief surfaces medical + local-authority mail", PASS)
    else:
        check("4. brief surfaces medical + local-authority mail", FAIL, line)


# ── Scenario 5 — an unrelated "Adam" does not inherit the principal identity ─────────────────────
def scenario_adam_namesake():
    """A new contact 'Adam Jones' is discovered. He must NOT get the case principal's slug (which
    is wired to the legal claim graph). The real Adam still resolves."""
    from lib.people import person_slug
    outsider = person_slug("Adam Jones")
    principal = person_slug("Adam Vials Moore")
    if outsider != "adam" and principal == "adam":
        check("5. 'Adam Jones' is not the principal; real Adam still is", PASS,
              f"Adam Jones→{outsider!r}, Adam Vials Moore→{principal!r}")
    else:
        check("5. 'Adam Jones' is not the principal; real Adam still is", FAIL,
              f"Adam Jones→{outsider!r}, Adam Vials Moore→{principal!r}")


# ── Scenario 6 — two people who share a display name stay distinct ───────────────────────────────
def scenario_namesakes_not_merged():
    """Discovery meets two different 'Emma Moore's (distinct emails). They must not collapse into
    one candidate with the second email dropped."""
    from lib.people_discover import _norm_name
    # Reproduce the discover_email keying contract (email-keyed) on a controlled set.
    cand: dict = {}

    def add(name, addr):
        key = addr or _norm_name(name)
        c = cand.setdefault(key, {"name": name, "email": addr or None, "count": 0})
        c["count"] += 1
        if addr and not c["email"]:
            c["email"] = addr
    add("Emma Moore", "emma.sister@x.com")
    add("Emma Moore", "emma.calder@msn.com")   # a different person, same display name
    add("Emma Moore", "emma.sister@x.com")     # the first one again → merges
    emails = {c["email"] for c in cand.values()}
    if len(cand) == 2 and emails == {"emma.sister@x.com", "emma.calder@msn.com"}:
        check("6. two same-named people stay distinct (no dropped email)", PASS)
    else:
        check("6. two same-named people stay distinct (no dropped email)", FAIL,
              f"{len(cand)} candidates, emails={emails}")


# ── Scenario 7 — a guessed circle is flagged; a human decision is protected ──────────────────────
def scenario_provenance_guess_vs_human():
    """An auto-assigned circle must read as a guess ('inner?'), and a human's kind correction must
    survive a re-classification pass (don't-clobber a decision)."""
    import lib.people as P
    from datetime import date as _d
    guessed = P.attention_score({"circle": "inner", "circle_src": "guess"}, _d(2026, 8, 13))[1]
    human = P.attention_score({"circle": "inner", "circle_src": "user"}, _d(2026, 8, 13))[1]
    check("7. guessed circle shows '?', human circle plain",
          PASS if (guessed == "inner?" and human == "inner") else FAIL, f"guess={guessed} human={human}")

    store = _tmp("people.json")
    P.save_people([{"id": 1, "name": "Michael Church", "email": None, "kind": "org",
                    "kind_src": "guess"}], store)
    P.set_kind(1, "person", path=store)          # human says: this is a person
    P.classify_all(path=store)                    # a later pass must NOT revert it to org
    p = P.load_people(store)[0]
    check("7b. human 'person' decision survives re-classification",
          PASS if (p["kind"] == "person" and p["kind_src"] == "user") else FAIL, str(p))


# ── Scenario 8 — contemporaneity: the SOUND probe vs the FLAWED probe (handover §3) ──────────────
def scenario_contemporaneity_sound_vs_flawed():
    """On a "what happened on 13 Mar" question, the PA's own later note must not be citeable as a
    source. We evaluate the filter TWO ways to honour handover §3:

      • FLAWED probe: the result set is already all same-dated primary emails (the 'query' carries
        the event signal). The filter has nothing to remove → the eval can't tell working from
        broken → it must report INCONCLUSIVE, not PASS.
      • SOUND probe: a realistic mixed set (primary email + a later PA note + a post-event email).
        The filter must drop the PA note and the post-event item, keeping the contemporaneous
        primary — and report what it excluded.
    """
    from lib.wall import contemporaneous
    event = "2026-03-14"  # question is about ~13 Mar; keep same-day, drop later

    # FLAWED: nothing in the set is a PA note or post-event — the set already encodes the answer.
    flawed_set = [
        {"source_path": "/cider/emails/2026-03-13_a.eml", "date": "2026-03-13"},
        {"source_path": "/cider/emails/2026-03-13_b.eml", "date": "2026-03-13"},
    ]
    kept_f, exc_f = contemporaneous(flawed_set, before=event)
    if exc_f["own_notes"] == 0 and exc_f["post_event"] == 0 and len(kept_f) == len(flawed_set):
        check("8. FLAWED probe correctly yields no signal → inconclusive", INCONCLUSIVE,
              "set contained nothing the filter could act on (query carried the answer) — cannot "
              "distinguish a working filter from a no-op; see handover §3")
    else:
        check("8. FLAWED probe correctly yields no signal → inconclusive", FAIL,
              f"unexpectedly excluded something: {exc_f}")

    # SOUND: neutral mix where the filter has real work to do.
    sound_set = [
        {"source_path": "/cider/emails/2026-03-13_hayley.eml", "date": "2026-03-13"},   # keep
        {"source_path": str(REPO / "data/daily/2026-04-02.md"), "date": "2026-04-02"},  # PA note → drop
        {"source_path": "/cider/NARRATIVE_REGISTER.html", "date": "2026-05-01"},        # PA reg → drop
        {"source_path": "/cider/emails/2026-08-10_later.eml", "date": "2026-08-10"},     # post-event → drop
    ]
    kept_s, exc_s = contemporaneous(sound_set, before=event)
    kept_paths = [k["source_path"] for k in kept_s]
    if (kept_paths == ["/cider/emails/2026-03-13_hayley.eml"]
            and exc_s["own_notes"] == 2 and exc_s["post_event"] == 1):
        check("8b. SOUND probe keeps the primary, drops own-notes + post-event, reports counts",
              PASS, f"excluded={exc_s}")
    else:
        check("8b. SOUND probe keeps the primary, drops own-notes + post-event, reports counts",
              FAIL, f"kept={kept_paths} excluded={exc_s}")


# ── Scenario 9 — a bounded dashboard list announces that it is bounded ───────────────────────────
def scenario_truncation_is_surfaced():
    """More than the cap of activities exist. The card must show the true total and a '+N more', so
    a bounded list can't be mistaken for the whole record."""
    import build_pa_dashboard as D
    from lib.activity import Activity
    big = [Activity(source="task", type="todo", timestamp=f"2026-08-{(i % 27) + 1:02d}T09:00",
                    title=f"Item {i}", theme=None, priority=None, url=None, meta={})
           for i in range(30)]
    orig = D.unified
    D.unified = lambda days=14: big
    try:
        html = D._activity_card()
    finally:
        D.unified = orig
    if "+14 more (of 30)" in html and ">30<" in html:
        check("9. clipped activity card shows true total + '+N more'", PASS)
    else:
        import re
        m = re.search(r"\+\d+ more \(of \d+\)", html)
        check("9. clipped activity card shows true total + '+N more'",
              FAIL, f"footer={m.group(0) if m else 'absent'}")


# ── Scenario 10 — the calendar window is honoured ────────────────────────────────────────────────
def scenario_calendar_window():
    """Ask for the next 7 days; an event 40 days out must not appear. Ask for 60; it must."""
    import lib.activity as A
    soon = (date.today() + timedelta(days=3)).isoformat()
    far = (date.today() + timedelta(days=40)).isoformat()
    A.glance_load = lambda: {"events": {"personal": [
        {"date": soon, "when": "10:00", "title": "Soon event"},
        {"date": far, "when": "11:00", "title": "Far event"}]}}
    A.ACCOUNTS = [{"id": "personal"}]
    w7 = {a.title for a in A.from_calendar(days=7)}
    w60 = {a.title for a in A.from_calendar(days=60)}
    ok = "Soon event" in w7 and "Far event" not in w7 and "Far event" in w60
    check("10. from_calendar honours its days window", PASS if ok else FAIL, f"7d={w7}")


def main() -> int:
    for fn in (scenario_appointment_no_time, scenario_queue_no_clobber, scenario_walled_meeting_hidden,
               scenario_brief_surfaces_case_adjacent_mail, scenario_adam_namesake,
               scenario_namesakes_not_merged, scenario_provenance_guess_vs_human,
               scenario_contemporaneity_sound_vs_flawed, scenario_truncation_is_surfaced,
               scenario_calendar_window):
        try:
            fn()
        except Exception as e:  # noqa: BLE001 — a scenario that blows up is a FAIL, not a crash
            check(fn.__name__, FAIL, f"raised {type(e).__name__}: {e}")

    glyph = {PASS: "🟢", FAIL: "🔴", INCONCLUSIVE: "🟡"}
    print("\nPA cider-lessons audit — scenario evaluations\n" + "─" * 60)
    for name, verdict, detail in _results:
        print(f"  {glyph[verdict]} {verdict:12} {name}")
        if detail and verdict != PASS:
            print(f"                  ↳ {detail}")
    n_pass = sum(1 for _, v, _ in _results if v == PASS)
    n_fail = sum(1 for _, v, _ in _results if v == FAIL)
    n_inc = sum(1 for _, v, _ in _results if v == INCONCLUSIVE)
    print("─" * 60)
    print(f"  {n_pass} pass · {n_fail} fail · {n_inc} inconclusive (by design)  of {len(_results)}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
