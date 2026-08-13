# PA audit against the cider handover lessons — 13 Aug 2026

## Status (updated 13 Aug 2026)

**Fixed:** 1, 2, 3 (`calevent` locked+atomic queue; `from_granola` wall guard) · 4, 5, 8
(`brief` medical/LA mail + "+N more"; `onedrive` bounded walk; `calevent` per-field provenance).
**Open:** 6, 7, 9–17. Next per the fix order below: 6 (focus contemporaneity enforced in code),
7 (`person_slug` "adam" short-circuit).

## Executive summary

Seventeen findings survived adversarial verification — **17 CONFIRMED, 0 PLAUSIBLE** — spread across all seven handover dimensions, with none rated high and twelve rated medium. The single most important issue is that the **proposed-events queue can silently and permanently lose a confirmed case appointment**: `lib/calevent.py` writes it non-atomically and mutates it from two unlocked processes, so a killed write or a clobbering interleave leaves a confirmed appointment that never re-surfaces and never lands on the calendar. Overall health is good: nothing corrupts the legal register itself, and every finding is a bounded, well-understood fix. The pattern is not broken logic but **missing provenance and missing "incomplete" signals** — guesses that read as facts, and bounded surfaces that read as complete — concentrated in the people layer, the dashboard cards, and the appointment queue.

## Findings

### 1. MED · CONFIRMED · `lib/calevent.py:104` — unlocked cross-process read-modify-write clobbers new proposals (permanent silent loss)

**Failure scenario.** `proposed_events.json` has two writers in separate processes with no file lock: `serve_dashboard.py` calls `set_status` on +add/dismiss clicks, while the monitor daemon appends newly-detected proposals. User clicks +add → dashboard `_load()` reads `{A}`; the daemon appends `B` and writes `{A,B}`; dashboard `_save()` then writes its stale `{A:confirmed}`, dropping `B`. Because the daemon already recorded B's key in `state['proposed_events']` at detection time, B is never re-proposed — the appointment is permanently and silently lost.

```python
    if hit:
        # drop dismissed/added rows so the surface stays to just live proposals + confirmations
        _save([p for p in items if (p.get("status") or "proposed") not in ("dismissed", "added")])
    return hit
```

**Verifier's note.** Two independent-process writers confirmed with no advisory lock (no `flock`/`fcntl` anywhere in `lib/`, `serve_dashboard.py`, or `monitor.py`). Loss is permanent because `watch_events` persists each fresh proposal's `candidate_key` to the `seen` set in the same cycle it writes the proposal (`monitor.py:207/215`), so a clobbered proposal is skipped forever. Collision window is the few-ms read→save gap and needs a manual +add to coincide with a detection cycle — low probability, but the consequence (silent permanent loss of a case appointment) justifies med.

**Fix.** Serialize writes with an advisory lock (`fcntl.flock`) held across read+write, or funnel all mutations through one owner. Minimally, re-read under lock immediately before `_save` and merge by key rather than overwriting the whole list.

### 2. MED · CONFIRMED · `lib/calevent.py:85` — proposed-events queue written non-atomically; corruption read as empty

**Failure scenario.** `_save` does a raw `write_text` (no temp-file+replace), unlike `taskstore._atomic_write` and `state.save_state`. The machine's documented normal state is near-full disk. If the process is killed or the disk fills mid-write, the file is left truncated. On the next call `_load` does `except (OSError, ValueError): return []`, so the corrupt file is silently read as an empty queue; `set_status()`/`pending()` then report success with no error, and calendar-capture creates nothing — confirmed appointments vanish silently.

```python
def _save(items: list[dict]) -> None:
    CACHE.write_text(json.dumps({"items": items}, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
```

**Verifier's note.** The sibling `taskstore._atomic_write` (lines 83–88) writes to `.tmp` and calls `tmp.replace(path)` with the comment "so a crash can't truncate the file" — the codebase knows the pattern and this store omits it. Same silent-no-op class as the disk-full `save_state` freeze that froze the iMessage watermark. Downgraded high→med: the confirmed queue is short-lived (drained promptly), so the corruption window is narrow.

**Fix.** Write via temp file + `os.replace` (reuse `taskstore._atomic_write`). Separately, `_load` should distinguish "missing" (ok, `[]`) from "present but unparseable" (raise/log) so a corrupt queue is never read as empty.

### 3. MED · CONFIRMED · `lib/activity.py:271` — `from_granola` surfaces walled case meetings on the default dashboard with no wall guard

**Failure scenario.** `lib/granola.py classify()` tags case meetings with `meta.context="case"` (in `wall.WALLED`) via title keywords like "police", "bail", "non-molestation". `from_granola` appends every cached item to `unified()` with no `is_walled` check — it never inspects `meta.context`. A Granola meeting titled "Bail review with Henry / DC Shotton" is cached with `meta.context="case"` and appears OPEN on the default "Recent activity" card — exactly the walled criminal-track content the wall module exists to keep off the default surface.

```python
        out.append(Activity(
            source="meeting", type=str(m.get("type") or "granola"),
            timestamp=m.get("timestamp"), title=str(m.get("title"))[:160],
            theme=m.get("theme"), priority=m.get("priority"), url=m.get("url"),
            meta={**(m.get("meta") or {}), "granola": True}))
```

**Verifier's note.** Live `data/granola_cache.json` has 34 items, 6 with `meta.context="case"` and 1 `medical` (both walled) — real titles like "VIALS MOORE CORE GROUP (DAD)", "Legal strategy — family court submission". The sibling `from_cider` (line 303) drops walled atoms, proving the guard is simply missing. Worse, `_ctx("family-court")` returns `"personal"` (not in `_CASE_THEMES`), so rows render `data-context="personal"` and any case-facet gate misses them. Severity corrected high→med: it is Adam's own private collapsed card, but the leak is live, ungated, and mislabeled.

**Fix.** Mirror `from_cider`: `from lib.wall import is_walled` and `if is_walled((m.get("meta") or {}).get("context") or m.get("theme")): continue` at the top of the loop.

### 4. MED · CONFIRMED · `lib/brief.py:106` — brief silently excludes medical & local-authority mail from orientation

**Failure scenario.** The brief's "Mail worth attention" line only ever lists contexts in `(legal, work, consulting)`. A message from a Sefton social worker (`context="local-authority"`) and one from the GP (`context="medical"`) — the most case-adjacent domains — are dropped entirely, never fed to the claude prompt or the deterministic fallback. Adam reads the hero brief, sees no mail flag, and concludes nothing in the inbox needs him.

```python
    weighted = sorted(
        msgs, key=lambda m: (0 if m.get("context") in ("legal", "work", "consulting") else 1,
                             m.get("date") or ""), reverse=False)
    top_msgs = [m for m in weighted if m.get("context") in ("legal", "work", "consulting")][:4]
```

**Verifier's note.** `lib/inbox._ctx_for` deterministically emits `medical` and `local-authority`, which are dropped from `top_msgs` with no "+N others" hint. Reachable and case-adjacent. Note the finder's data claim is not currently manifest: today's `inbox_cache.json` has no medical/LA items (31 personal, 13 legal, 1 consulting) — the defect fires when such mail arrives, which is routine for this project. (Also: `"work"` in the surfaced set is never produced by inbox at all.)

**Fix.** Include `"local-authority"` and `"medical"` in the surfaced set, or keep the ranking but append a "+N other-context messages" line to `_situation_text`/`_fallback` so the brief cannot read as complete when mail was excluded.

### 5. MED · CONFIRMED · `lib/onedrive.py:43` — unbounded `os.walk` over the entire OneDrive sync root, run every 15 min

**Failure scenario.** `sync_roots()` globs every `~/Library/CloudStorage/OneDrive*` root (institutional SharePoint libraries can hold tens of thousands of files). `recent_files()` does a full, depth-unbounded `os.walk` of each tree, `stat()`-ing every file, and truncates only *after* the walk (`return found[:limit]`). The `limit`/`days` args give false boundedness — they never shrink the walk. Reached via `unified()` → `build_pa_dashboard.py`, which the monitor re-runs every 15 min, driving repeated File-Provider directory hydration across every subtree on a machine already under disk/IO pressure.

```python
    roots = roots if roots is not None else sync_roots()
    cutoff = datetime.now() - timedelta(days=days)
    found: list[dict] = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune hidden dirs in place so we don't descend into them.
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
```

**Verifier's note.** Only hidden dirs pruned; no depth cap, no file-count cap, no SF_DATALESS/placeholder skip. Caller chain confirmed: `from_files` → `recent_files`; `unified()` → `build_pa_dashboard.py:332/397`; `monitor.py:429` re-runs it throttled to `SURFACE_REFRESH_MIN=15`. The subprocess `timeout=60` bounds wall time but not the IO enumeration triggered each cycle. Only `stat` is called (no content download), so no 4.7 GB-style pull, but it is the exact unbounded-walk pattern v1 warns about.

**Fix.** Bound the walk: a `max_files` scan cap with early stop, a max depth (prune `dirnames` when too deep), and optionally skip dataless placeholder dirs via `os.stat(dirpath).st_flags & SF_DATALESS`. Apply the days-cutoff and limit inside the loop with early termination.

### 6. MED · CONFIRMED · `skills/focus/SKILL.md:58` — contemporaneity/self-citation guard is advisory-only, never enforced in code

**Failure scenario.** `authored_before`/`authored_after` appear in no Python file — the only exclusion of the PA's own notes is conditional prose. The enforced filter, `lib.wall.filter_results`, gates by track/context, not authorship, so it never excludes the PA's own briefs/notes. On a Case focus, an agent asks "what did Hayley say on 13 Mar"; `store_search` returns the PA's own note summarising that email ranked *above* the primary email (the summary reads more fluently), and the PA's summary of its own finding is cited back as the source.

```python
of its own finding. When you're after **what actually happened**, pass `store_search`'s
`authored_before`/`authored_after` to keep evidence contemporaneous with the event, and prefer the
```

**Verifier's note.** grep finds `authored_before`/`authored_after` only at `skills/focus/SKILL.md:59` — zero in any `.py`. `filter_results`/`_chunk_is_walled` (lib/wall.py:48–55) key solely on track/context/source_path; with `allow_case=True` `filter_results` returns everything, so PA-authored case-track notes can outrank the primary source. The contemporaneity discipline exists only as prose the agent may skip.

**Fix.** Add an authored-window / `is_own_note` exclusion to the recall helper (extend `lib.wall` to drop chunks whose `source_path` marks a PA-authored note when the question is "what happened"), and default `authored_before` to the event date on the focus recall path.

### 7. MED · CONFIRMED · `lib/people.py:104` — `person_slug` collapses ANY first-name "Adam" to the principal slug `adam`

**Failure scenario.** For the other three principals the guard requires a `vials`/`moore` surname token, but for Adam the `toks[0] == "adam"` short-circuit fires on the first name alone. A discovered contact "Adam Jones" or "Adam Kessler" gets `slug == "adam"`, the case principal's shared cider-store identity. In `build_pa_dashboard.py:422-430` that node is tagged `s:adam` and wired to `cider.person_claims("adam")` — the principal's sensitive legal claim graph. An unrelated third party is rendered bearing Adam Vials Moore's case claims.

```python
    if toks[0] in _PRINCIPAL_SLUG and (toks[0] == "adam" or "vials" in low or "moore" in low):
        return _PRINCIPAL_SLUG[toks[0]]
```

**Verifier's note.** Confirmed downstream: `_PRINCIPAL_SLUGS={adam,cora,gwen,isaac}`; nodes whose slug is in that set are wired to `cider.person_claims(slug)` and tagged `s:adam`, so "Adam Jones" would render bearing the principal's claims. Gated behind the private case toggle (off by default), limiting exposure — med.

**Fix.** Remove the `toks[0] == "adam" or` short-circuit so Adam is matched on the same surname evidence as the others (`... and "vials" in low and "moore" in low`), or match the full name against a curated principal-name allowlist. "Adam Jones" then falls through to `adam-jones`.

### 8. MED · CONFIRMED · `lib/calevent.py:69` — event title/location/all_day guessed with no provenance; `all_day` silently defaults on time-parse miss

**Failure scenario.** For an SMS "Your dentist appointment is confirmed for 14 Aug, please arrive 10 mins early", `_find_time` finds no am/pm or HH:MM, so `has_time=False` and `all_day` becomes `True` — a real timed appointment is silently proposed as an ALL-DAY block purely because the time wasn't parsed, with nothing recording that `all_day` is a parse-fallback. Likewise `_clean_title` returns the bare fallback "Appointment" and `_location` guesses a venue; all three are shown on the confirm card identically to values lifted verbatim from the message. Adam confirms on a guess he can't distinguish from fact, and a wrong event lands on the calendar.

```python
    return {"title": _clean_title(prop.get("snippet", "")),
            "start": start, "end": end, "all_day": not has_time,
            "location": _location(prop.get("snippet", "")),
```

**Verifier's note.** `all_day = not has_time`; `has_time` is None whenever no clock time is present, so a timed appointment silently becomes all-day with no marker of parse-fallback vs a genuine all-day cue. `calendar-capture SKILL.md:31-36` consumes these fields verbatim onto the confirm card before the write to fairresconman.

**Fix.** Carry per-field provenance out of `event_fields`: `all_day_reason='no-time-parsed'` when `has_time` is False, `title_src='fallback'` on the "Appointment" default, `location_src='guessed'`; render these on the confirm card so guessed fields are flagged before Adam approves the write.

### 9. MED · CONFIRMED · `lib/people.py:272` — guessed proximity circle surfaced as attention reason with no "guessed" marker

**Failure scenario.** `circle` is set by `circle_for(interactions)`, a pure volume guess whose docstring says "the count is a starting guess, not the truth". A high-volume past correspondent (≥500 emails) is auto-assigned `circle='inner'`, gains +18 attention and `reason='inner'`, floats to the top of `ranked_people`, and `brief.py:159` prints "Name (inner)" — character-identical to a person Adam hand-set to inner. A heavily-emailed ex-colleague outranks a rarely-texted close relative, and Adam can't see it was auto-guessed.

```python
    circle = p.get("circle")
    s += _CIRCLE_ATTN.get(circle, 0)
    if circle in ("inner", "close") and not reason:
        reason = circle
```

**Verifier's note.** `set_fields` writes the SAME `p['circle']` on human correction; no provenance field exists; the ranking can invert exactly as the docstring warns. Confirmed.

**Fix.** Record circle provenance (`circle_src='guess'` from `circle_for`, `'user'` from `set_fields`) and reflect it in `_reason` (e.g. `'inner?'` / `'inner (guessed)'`) so the brief/People card shows guessed proximity distinctly.

### 10. MED · CONFIRMED · `lib/people.py:156` — person `kind` guess and human assertion share one field, no provenance

**Failure scenario.** `classify_kind` is a heuristic ("Best-effort", "Auto-guessed on seed"). A contact whose surname is an org token — "Michael Church", "Grace Society" — matches `\bchurch\b`/`\bsociety\b` and is stored `kind='org'`; "A. Smith" hits the `.`→org rule. That guessed value is written to the same `p['kind']` field that `set_kind()`/`set_fields()` write on human confirmation. No field records whether `kind` was machine-guessed or asserted, and `classify_all()` only fills when `not p.get('kind')`, so a guess is frozen with the credibility of a fact — the exact cider hole. The 🏢 badge renders guess and assertion identically.

```python
    rec = {"id": _next_id(people), "name": name, "email": email, "context": context,
           "kind": classify_kind(name, email), "priority": "normal",
```

**Verifier's note.** grep for `_src`/`provenance`/`guessed` in `lib/people.py` finds none; `people_discover.main:229` renders 🏢 identically regardless of source. A machine guess is data-indistinguishable from a confirmed fact.

**Fix.** Store provenance alongside the value (`rec['kind_src']='guess'` in upsert/classify_all; `set_kind()`/`set_fields()` stamp `kind_src='user'`), surface it (badge "org?"/"guessed" vs plain "org"), and let `classify_all` re-derive values still marked `'guess'`.

### 11. MED · CONFIRMED · `lib/people_discover.py:111` — discovery keys candidates by name; distinct same-named people collapse, 2nd email lost

**Failure scenario.** Adam's sister emails as "Emma Moore" `<emma.sister@…>` and a professional contact also displays as "Emma Moore" `<emma.calder@msn.com>`. `discover_email()` keys both on `_norm_name` → "emma moore", so they merge into ONE candidate: counts are summed and only the first email is kept. `candidates()`/`add_people()` upsert a single person for two humans; the second is never captured and their email is discarded — the cider `emmacalder@msn.com` near-miss the register explicitly warns about.

```python
        key = _norm_name(name)                              # key by NAME so same person merges
        c = cand.setdefault(key, {"name": name, "email": addr or None, "count": 0, "sent": False})
        c["count"] += 1
        c["sent"] = c["sent"] or sent
        if addr and not c["email"]:
```

**Verifier's note.** `if addr and not c["email"]` fills email only when empty, so a second distinct address under the same display name is discarded and two humans merge. No downstream guard. This is the contact-discovery/reconnect layer (people.json nudges), not the legal claim graph, so med. (Closely related to finding 12 — same name-keying root cause, different function.)

**Fix.** Key candidates by email when present, falling back to name only when no address exists (`key = addr or _norm_name(name)`); when distinct emails share a display name, keep them separate or surface the collision count rather than dropping the second address.

### 12. MED · CONFIRMED · `lib/people_discover.py:173` — `candidates()` `offer()` re-merges across email+iMessage by name; no cap, no suppressed-count report

**Failure scenario.** `offer()` merges candidates from email AND iMessage on `_norm_name` alone. An email "John Smith" and an iMessage-resolved "John Smith" (a different phone/person) fold into one candidate with summed counts and a single email/context. There is no cap on how many raw interactions/sources fold into a name-key and no reporting of how many distinct sources collapsed, so a common name silently absorbs several humans; the caller sees only an inflated `count`.

```python
        key = _norm_name(name)
        if not key or key in existing:
            return
        if email and email.lower() in existing_emails:
            return
        c = merged.setdefault(key, {"name": name, "email": email, "count": 0,
                                    "sources": set(), "sent": sent})
        c["count"] += count
```

**Verifier's note.** The only email guard rejects emails already in `existing_emails` (already-tracked people); it does not compare two *new* candidates' emails, so cross-source collisions fold together with email frozen at first. No cap and no collision reporting. Reachability needs a cross-source name collision (plausible for common names), so med. (Same root cause as finding 11, different function — kept separate per line/function.)

**Fix.** Disambiguate the merge key by email when available; when multiple distinct emails/handles map to one display name, keep them separate or attach the collapsed distinct-identifier count so a suspiciously large cluster is visible instead of a silent many→one.

### 13. LOW · CONFIRMED · `lib/activity.py:283` — `from_granola` silently drops date-less meetings under the day window

**Failure scenario.** `unified()` always calls `from_granola(days=14)`, so `cutoff` is always set. A `granola_cache.json` entry with a real title but a null timestamp (the agent-written cache can omit the date) yields `("")[:10] == ""`, which is `< cutoff`, so the meeting is filtered out of the stream and the dashboard entirely — a meeting that happened reads as "no such meeting". This also defeats `_sort_key` (built to keep undated items at the bottom, not drop them) and contradicts `from_cider`, which keeps undated atoms.

```python
    return [a for a in out if not cutoff or (a.timestamp or "")[:10] >= cutoff]
```

**Verifier's note.** `days` is 14 or 21 at both call sites, both truthy, so a real ISO cutoff is always computed; a None/missing timestamp maps to `""` and is dropped. `from_cider` (299–315) applies no cutoff and `_sort_key` keeps undated items last, confirming the inconsistency.

**Fix.** Keep undated items: `return [a for a in out if not cutoff or not a.timestamp or a.timestamp[:10] >= cutoff]` — mirroring `from_cider`, so a dateless meeting still surfaces (sorted last).

### 14. LOW · CONFIRMED · `build_pa_dashboard.py:340` — recent-activity card truncates to 16 with empty count and no "+more"

**Failure scenario.** `unified(days=14)` returns e.g. 53 activities; the card renders only `stream[:16]` into the DOM (the rest are not emitted, not merely hidden) and passes `count=""` so the header shows no figure. Unlike the Messages card, which renders hidden rows plus an explicit "+N more" control, the activity card gives no indication items were dropped. The bounded list reads as "this is the recent activity" when it is only the newest 16.

```python
        for a in stream[:16])
    return _card("activity", "Recent activity", "", f'<ul class="rows">{rows}</ul>',
                 collapsed=True)
```

**Verifier's note.** `_card` omits the count span when falsy, so no figure shows; no "+N more" control, unlike `_messages_card`. Empirically `unified(days=14)` returns 53 today, so 37 are dropped from the DOM with zero indication — currently manifest.

**Fix.** Pass the true total as the card count (`str(len(stream))`) and/or add a "+N more" affordance like `_messages_card`.

### 15. LOW · CONFIRMED · `build_pa_dashboard.py:397` — Nest field view caps at 80 activities / 40 people with no hole indicator

**Failure scenario.** The Nest builds nodes from `unified(days=21)[:80]` and `ranked_people(...)[:40]`. With more than those, the overflow is silently omitted from the spatial map and from the per-container counts (`ctr-n` shows only survivors). A user tracing links across everything sees a bounded subgraph presented as the whole picture — an item connecting only to a dropped node appears to connect to nothing, with no "+N not shown" marker.

```python
    for a in unified(days=21)[:80]:
```

**Verifier's note.** The people cap is live now: `load_people()=90` and `ranked_people()=90`, so 50 people are silently omitted. The activity cap is not currently exceeded (57 < 80) but the people-side truncation confirms the defect.

**Fix.** Surface the truncation (a per-context or global "+N not shown" chip when node count exceeds the cap) or raise/remove the cap; at minimum record how many were dropped so container counts don't imply completeness.

### 16. LOW · CONFIRMED · `lib/activity.py:118` — `from_calendar` ignores its `days` window param (answers a wider window)

**Failure scenario.** `days` is accepted and forwarded by `unified(days)`, but the body never references it — every event in `glance_cache.json` is emitted regardless of horizon. So `unified(days=7)` does not return a 7-day calendar window; it returns whatever span the cache holds (14+ days). A caller asking for "the next 7 days" silently gets events 10–14 days out. `from_files(days)` *does* honour `days`, so the two sources on the same stream apply different, undisclosed horizons.

```python
def from_calendar(days: int = 14) -> list[Activity]:
    """Upcoming events across both calendars, as activities — from the glance cache (no network)."""
    events_by_acct = glance_load().get("events", {})
```

**Verifier's note.** The body (120–146) never references `days`; `unified()` forwards it at line 326 with no effect, while `from_files(days)` honours it. Confirmed as a code fact, but the effect is over-inclusion (a superset), not omission — hence low.

**Fix.** Apply the window: filter to events whose parsed date falls in `[today, today+days]`; or, if the glance cache horizon is authoritative, drop the `days` param and document that so callers don't assume it bounds the result.

### 17. LOW · CONFIRMED · `lib/remindpush.py:68` — swallowed `remindctl` failure after create → duplicate reminders

**Failure scenario.** The module's contract is "a local map tracks `task_id → reminder id` so re-runs never duplicate." `_add` returns the new id, but if `remindctl` creates the reminder yet returns blank JSON (`json.loads('{}').get('id') → None`), or times out (20 s) *after* creating the item, `_add` returns None. In `sync()` the guard `if rid:` is then False, so the `task_id` is never recorded in `pushed`; next sync the task is still open and absent, so `_add` runs again → a second identical reminder. Each cycle adds another, spamming the "PA Tasks" list on iPhone/Watch.

```python
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (json.loads(out.stdout or "{}") or {}).get("id")
    except (subprocess.SubprocessError, OSError, ValueError):
        return None
```

**Verifier's note.** The module stamps each reminder with url `pa-task:<id>` for provenance and promises "re-runs never duplicate", but nothing queries existing PA reminders by that url before adding (`_completed_pa_reminders` only lists completed ones). Corrected med→low: fires only when `remindctl` creates-but-fails-to-report an id; the happy path returns and records the id. Impact is duplicate reminders (annoyance), not data loss.

**Fix.** Distinguish "create failed" from "created but id unparsed": check the subprocess returncode, and on ambiguous success query `remindctl` for a reminder whose `url == pa-task:<id>` before re-adding (idempotent by the url the module already stamps).

## Clean dimensions

None. All seven audited dimensions produced at least one surviving finding — there is no dimension the code already handles cleanly end-to-end.

## Recommended fix order

Ordered by severity × how central the module is to daily use:

1. **`lib/calevent.py:104` (finding 1)** — lock/serialize proposed-events writes. Permanent silent loss of a confirmed case appointment; the appointment queue is core daily flow.
2. **`lib/calevent.py:85` (finding 2)** — atomic write + distinguish missing-vs-corrupt on load. Same store, same silent-loss class; pair it with the fix above.
3. **`lib/activity.py:271` (finding 3)** — add the `is_walled` guard to `from_granola`. Walled criminal-track content live on the default dashboard, the primary surface.
4. **`lib/brief.py:106` (finding 4)** — surface or count medical/LA mail. The hero brief reads as complete while dropping the most case-adjacent domains.
5. **`lib/calevent.py:69` (finding 8)** — per-field provenance on proposed events. Feeds the same confirm→calendar write path as findings 1–2.
6. **`lib/onedrive.py:43` (finding 5)** — bound the walk. Runs every 15 min under disk/IO pressure; central to the always-on loop.
7. **`skills/focus/SKILL.md:58` (finding 6)** — make contemporaneity enforceable in the recall helper. Affects Case-focus evidence integrity.
8. **`lib/people.py:104` (finding 7)** — remove the `adam` first-name short-circuit. Mis-attributes the principal's legal claim graph; gated, so lower urgency.
9. **`lib/people.py:272` & `:156` (findings 9, 10)** — add `circle_src`/`kind_src` provenance. Same module, do together; guesses reading as facts in the people layer.
10. **`lib/people_discover.py:111` & `:173` (findings 11, 12)** — key by email, report collisions. Same root cause across two functions; fix together.
11. **`lib/activity.py:283` (finding 13)** — keep undated granola meetings. Quick one-line parity fix with `from_cider`.
12. **`build_pa_dashboard.py:340` & `:397` (findings 14, 15)** — show true totals / "+N not shown". Dashboard completeness signals; low risk.
13. **`lib/activity.py:118` (finding 16)** — honour or drop the `days` param. Over-inclusion only.
14. **`lib/remindpush.py:68` (finding 17)** — idempotent create by `pa-task:<id>` url. Conditional edge; annoyance, not loss.
