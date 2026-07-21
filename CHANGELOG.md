# Changelog

All notable changes to this project. Successor to the legacy `updates.txt` habit.
Format loosely follows Keep a Changelog; dates are absolute.

## [Unreleased] — source integrations
- **Westminster / Enact work comms (on-demand)**: `lib/cdp.py` — a zero-dependency stdlib
  Chrome DevTools Protocol client — reads the visible text of Adam's already-logged-in
  dedicated Enact Chrome (remote-debug :9222). `skills/work-pull/` summarises Outlook
  mail+calendar, Teams, and Slack (Notch8) with no credentials/scraping. Read-only, only the
  4 work URLs, on-demand (a live browser can't be a daemon). Verified against live tabs.
- **Interactive desktop dashboard**: the localhost surface is now additive + completion-
  reporting — a capture box (title/theme/energy/priority) and a per-task ✓ button. The
  loopback server handles `/capture` + `/complete` (Post/Redirect/Get), rebuilding the page.
  `lib.taskstore.complete_task` records `completed_at` (also closes the month-scoping gap).
- **Desktop surface**: `serve_dashboard.py` + `com.adamvialsmoore.pa-dashboard` launch
  agent serve the dashboard at http://127.0.0.1:8787 (loopback only), auto-refreshing every
  60s; the monitor keeps the HTML current. A real always-on desktop glance to keep open.
- **Dynamic monitoring layer (ADR-002) — the constant companion:** `lib/state.py`
  (persistent state + dedup/rate-limit ledger) + `skills/monitor/monitor.py`, an always-on
  loop that watches mail/calendar/deadlines, reacts to genuinely new events (chatty, but
  dedup means once-ever per event), and keeps surfaces fresh. LLM-free watching; nudges reuse
  nudge.sh. `com.adamvialsmoore.pa-monitor` launch agent; `autonomy.yaml` `monitor:` config.
  First run seeds silently. Smoke coverage added (state + monitor). ruff clean.
- **Test harness**: `tests/smoke.py` — one-command end-to-end smoke test (10 checks, safe:
  temp store, read-only sources, no sends). Documented at the top of TESTING.md.
- **Polish**: unified activity timeline now sorts **soonest-first** (undated last); the daily
  nudge auto-weaves an energy-aware **"Easiest start: …"** (lowest-activation task, via
  `skills/checkin-daily/quick_win.py`).
- **Salvage from prior repos (4 items, built in parallel):**
  - *Energy + breakdown*: task store gains `energy` (low/med/high), `estimate_min`, and
    `steps`; `task-capture` gets `--energy/--estimate/--step`; `focus` shows effort + first
    step and adds `--energy low` quick-wins filter. (from llm-pa / llm-pa-ver ADHD taxonomy)
  - *Reflection prompt banks*: `extracted/reflection_prompts.json` — 36 PDA-aware prompts in
    5 groups (activation/breakdown/self_care/reflection/reframe), woven one-per-session into
    the check-ins. (salvaged from llm-pa-ver coaching prompts)
  - *Unified Activity model*: `lib/activity.py` normalizes tasks/calendar/mail/files into one
    stream; dashboard gains an additive "Recent activity" timeline — the seed of the ZigZag
    associative-trails idea. (from idea-tracker-mcp-dashboard Activity Hub)
  - document_vault reviewed and skipped (unrelated dead-man's-switch mailer).
- **Focus (theme + priority)**: task store gains `theme` (free project tag) and `priority`
  (high/normal/low); `task-capture` accepts `--theme`/`--priority`. New `focus` skill
  (`skills/focus/focus.py`) renders one theme's tasks + related dates/messages and can push a
  synced `Focus` Apple Note + Signal summary — the deep-focus complement to the overview.

- **Signal nudges → phone: LIVE** (2026-07-20). signal-cli 0.14.6 (ARM) linked; a launch
  agent (`com.adamvialsmoore.signal-cli-daemon`, RunAtLoad+KeepAlive) serves the JSON-RPC
  API on `127.0.0.1:8080`; OpenClaw's Signal channel enabled; `nudge.env` routes via
  `openclaw message send`. Test nudges confirmed received on the phone. Repo carries a
  number-less plist template; SIGNAL_SETUP.md rewritten to the working setup.

- **Apple Notes** (`lib/applenotes.py`): capture mirrors into a dedicated PA-owned note
  (`PA Inbox`) — never edits Adam's existing notes. Read helpers (`list_titles`, `read_note`)
  available for surfacing list content, with the guardrail that case/medical content is never
  pushed into PA outputs. `task-capture` now writes local store + PA Inbox (best-effort,
  `--no-notes` to skip). AppleScript via stdin+argv (no escaping); ruff clean; live-tested.
- **Work OneDrive/SharePoint** (`lib/onedrive.py`): read-only, metadata-only view of recently
  touched files in the official OneDrive sync folder (sanctioned client path — no scraping,
  no credentials). Lists name/folder/when only; never copies document contents. Live-tested
  against the University of Westminster sync root; ruff clean.
- See `ROADMAP.md` for remaining work sources (Outlook, Teams, Slack) and Signal/iPhone.

## [2.0.0] — agent-native overhaul (2026-07-20)

**Migration summary.** The 2024 FastAPI + React + SQLite app is retired and rebuilt as a set
of Claude Code skills over adam-local / `gog` / `himalaya` / Granola / Signal — no web server,
no database, no bespoke OAuth. Task store is local markdown/JSON; the PA renders its own
dashboard (separate from CIDER); check-ins run on launchd with skippable Signal nudges;
autonomy is governed by `autonomy.yaml`. The legacy app is preserved in `legacy/` and at the
`v1-legacy` tag / `archive/2024-fastapi-react` branch. History was rewritten to purge
committed secrets + a vendored `node_modules` (force-pushed). Full detail by phase below.


### Phase 0 — Audit & repo hygiene (2026-07-19)
- Full-history secret scan (gitleaks): 6 hits — Anthropic API key + Google OAuth
  client_secret/tokens. Reported in `PHASE0_SECURITY_REPORT.md` (kept local, git-ignored).
- Rewrote history with `git filter-repo`: purged secrets, the 26-row personal `test.db`,
  and the committed `frontend/node_modules`. `.git` 118 MB → 716 KB; tracked files
  77,882 → 50; gitleaks now clean. Force-pushed `main`.
- Credential rotation **declined** by owner (existing infrastructure kept) — accepted risk.
- Populated the empty root `.gitignore` (secrets, data, node_modules).
- Extracted legacy assets to `extracted/`: prompt bank, action-learning questions, taxonomy.
- Produced `INVENTORY.md` (legacy archaeology + legacy→target mapping).

### Phase 1 — ADR (2026-07-19)
- `ADR-001-agent-native-pa.md` accepted: Claude Code runtime, local-file task store, the
  PA's own dashboard (decoupled from CIDER), both Gmail accounts kept separate, iMessage
  read-only, Signal + calendar nudges, four-tier `autonomy.yaml`.

### Phase 2 — Build (in progress, 2026-07-19)
- Tagged `v1-legacy` and branched `archive/2024-fastapi-react` from the clean HEAD (pushed).
- Moved the 2024 FastAPI/React app to `legacy/` (preserved, not live).
- Added `autonomy.yaml`, `skills/`, new root scaffolding, and rewrote `README.md`.
- **Skill 1 — `task-capture`**: friction-free capture to `data/tasks.json` via a
  ruff-clean Python helper (atomic write, corrupt-store guard). `.claude/skills` symlink
  makes skills discoverable by Claude Code. Demoed with 3 captures.
- **Shared `lib/taskstore.py`**: single owner of the store; `save_tasks()` rewrites the
  JSON *and* a human-readable `data/tasks.md` mirror so they never drift. `capture.py`
  refactored to a thin CLI over it.
- **Skill 2 — `build_pa_dashboard.py`**: renders the store to a self-contained, theme-aware
  `data/PA_DASHBOARD.html` — the PA's own surface, decoupled from CIDER. Calm/PDA-aware
  layout (small wins, no debt ledger). Demoed visually with 4 tasks.
- **Skill 3 — `checkin-daily`**: `glance.py` gathers today's calendar (both accounts, via
  gog), a *prioritised* inbox shortlist (both accounts via himalaya, noise counted+hidden),
  and due tasks; writes a `data/daily/<date>.md` stub. `SKILL.md` frames it as a skippable
  invitation and records up-to-three intentions. Read-only; ruff clean. Demoed against live
  calendar + inboxes.
- **Shared `lib/comms.py`**: single home for the account list + gog/himalaya read plumbing
  + inbox noise heuristic. `glance.py` refactored onto it; noise filter tuned (safe
  marketing phrases added).
- **Skill 4 — `comms-triage`**: `triage.py` prints an actionable per-account shortlist
  (each line carries an id, e.g. `[fairres #1721]`). `SKILL.md` reads only chosen bodies,
  proposes drafts to `data/drafts/` (`propose_draft`, autonomous-flagged), and saves into
  the live mailbox only on confirmation (`save_gmail_draft`, confirm-required) — never
  sends. autonomy.yaml updated to split those two. Demoed against live inboxes.
- **Skill 5 — `checkin-weekly`**: `horizon.py` — 14-day deadline horizon (both calendars,
  separate) + loose-thread sweep (overdue/due-this-week tasks); writes `data/weekly/<YYYY-Www>.md`.
  SKILL.md invites ONE skippable action-learning question. Read-only; ruff clean; live-tested.
- **Skill 6 — `checkin-monthly`**: `review.py` — "what changed" (open/done by category,
  small wins), month-ahead highlights (both accounts, separate), category cleanup of undated
  tasks; writes `data/monthly/<YYYY-MM>.md`. Read-only; ruff clean; live-tested.
  Known gap: store has no `completed_at`, so "done this month" can't be filtered yet
  (follow-up: add completion timestamps when a task-complete action lands).
- **Skill 7 — `quarterly-review`**: `assemble.py` gathers deterministic local sources
  (daily/weekly/monthly notes, task activity by category, read-only git log) into a
  `data/reviews/<quarter>.md` digest; SKILL.md then enriches with Granola meetings + the
  evidence store (MCP at runtime) and drafts a review in Adam's voice. Draft-only, never
  sends. Read-only assemble; ruff clean; live-tested. **Phase 2 skills complete.**

### Phase 3 — Schedules & nudges (authored 2026-07-20, awaiting install sign-off)
- `schedule/run_checkin.sh <cadence>`: scheduled half of a check-in — runs the deterministic
  prep (refreshes the durable note) then sends ONE skippable Signal invitation. Never runs
  the interactive check-in (ignoring the nudge = zero-consequence skip). shellcheck clean.
- `schedule/nudge.sh`: configurable Signal sender, **safe by default** — sends nothing until
  `schedule/nudge.env` (git-ignored) sets `NUDGE_CMD` (OpenClaw/send_signal_alert) or
  `SIGNAL_FROM`+`SIGNAL_TO` (signal-cli). Unconfigured = logs intended message, no send.
- Three launchd plists (`schedule/launchagents/`, house-style, no RunAtLoad): daily 07:30,
  weekly Mon 08:00, monthly 1st 09:00. plutil-valid.
- `schedule/README.md` + `nudge.env.example`. DRY_RUN pipeline verified end-to-end (prep ran,
  note refreshed, nudge no-op'd — nothing sent, nothing installed).
- Calendar-reminder channel documented (recurring events, confirm-required) — created on OK.
- Installed: all three launchd jobs loaded in ~/Library/LaunchAgents; daily job test-fired
  via launchctl (exit 0). Nudges remain no-op until `nudge.env` is wired.

### Phase 4 — Decommission (2026-07-20)
- Verified + pushed `v1-legacy` tag and `archive/2024-fastapi-react` branch (legacy app
  preserved secret-clean).
- Legacy 2024 app relocated to `legacy/` on `main` (per ADR-001; `npm install` regenerates
  the removed `node_modules`).
- README rewritten: what the system is now, a one-command quick start, and the migration
  note pointing at the legacy tag.
- This release header is the final migration summary. **Overhaul complete.**
