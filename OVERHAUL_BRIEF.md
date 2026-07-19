# LLM-PA → Agent-Native Overhaul Brief

**For:** Claude Code, working in the local clone of github.com/adammoore/llm-pa
(confirm path and remote before anything else)
**Owner:** Adam Vials Moore (adammoore)
**Read this whole file before touching anything. Work in phases. Stop for sign-off
at each GATE.**

## Mission

Rebuild the 2024 "LLM Personal Assistant" as an agent-native system inside the
existing CIDER / adam-local ecosystem. Preserve the original intent — an
ADHD-supportive PA that initiates, checks in, and keeps calendar and communications
visible — while retiring the bespoke FastAPI + React + OAuth stack that modern
tooling makes unnecessary.

## Repo strategy (DECIDED)

The overhaul happens in place at github.com/adammoore/llm-pa. The legacy
FastAPI/React app is archived *within* this repo, not moved elsewhere:

- Tag current HEAD as `v1-legacy` and create branch `archive/2024-fastapi-react`
  before any restructuring.
- On main, either move surviving legacy code to `legacy/` or delete it and rely on
  the archive branch — propose one of the two at the Phase 1 GATE.
- New root layout: `skills/`, `data/`, `ADR/`, `autonomy.yaml`,
  `OVERHAUL_BRIEF.md`, `CHANGELOG.md`, rewritten `README.md` with a migration note
  pointing at the tag.

## What the legacy system was

- FastAPI backend + React/MUI frontend + SQLite (async SQLAlchemy)
- Direct Anthropic completions calls (claude-v1 era, hand-rolled headers)
- Google Calendar via manual OAuth2 (client_secret.json / token.json)
- APScheduler for daily/weekly/monthly prompt triggers
- Abandoned Any.do and half-finished TickTick integrations
- A prompt bank + action-learning question set (valuable — extract these)

Treat the code as an archaeology site, not a foundation.

## What exists now (build on this, don't duplicate)

- Claude Code as runtime: skills, hooks, scheduled execution
- adam-local MCP server: daily_sweep, regenerate_dashboard, daily notes
  read/write, evidence store, deadlines, granola meeting tools, analyse_whatsapp,
  send_signal_alert, gog wrappers
- gog CLI for Gmail + Google Calendar across multiple accounts (no browser, no
  OAuth dance)
- himalaya email MCP wrapper for reading/drafting
- Granola for meeting transcripts and notes
- OpenClaw with Signal integration (Mac + iPhone over Tailscale) for nudges and
  capture
- CIDER dashboard: canonical HTML situation dashboard regenerated from sweep data

Discover actual tool names via the MCP tool listing at runtime; the above are
indicative.

## Core goals to preserve

1. **Initiation support** — prompts to start the day/week/month at set boundaries.
2. **Progress check-ins** — gentle, skippable, one question at a time. Never a
   guilt audit.
3. **Calendar awareness** — work/home/social across all connected Google accounts.
4. **Communication triage** — inbox summaries and draft-ready replies; WhatsApp
   via export analysis; iMessage only if approved (see Open Decisions).
5. **Review & reporting material** — quarterly review drafts assembled from real
   activity: daily notes, granola meetings, git history, evidence store.
6. **Action-learning reflection** — the "Twenty Questions" bank woven into
   weekly/monthly check-ins, one question per session.
7. **Explicit autonomy tiers** — the old "AI Autonomy" toggle, made real and
   granular.

## Design principles (neurodivergent-first, PDA-aware)

- Invitations, not demands. "Want to look at today?" beats "Complete your daily
  review."
- One question at a time. Always a skip/later path with zero consequence.
- Externalize memory: every session leaves a durable trace the dashboard can
  render.
- Low activation energy: one command or one Signal tap starts anything.
- Small wins made visible; completed items acknowledged briefly, never itemized
  as debt.

## Target architecture (proposal — push back if you see better)

- **Runtime:** scheduled Claude Code sessions (launchd on macOS) + on-demand. No
  web server. No React.
- **Skills** (one per file, built one at a time):
  - `checkin-daily` — morning framing, top-3 intentions, calendar + inbox glance
  - `checkin-weekly` — one action-learning question, deadline horizon,
    loose-thread sweep
  - `checkin-monthly` — goals review, category cleanup, "what changed"
  - `comms-triage` — summarize inboxes via gog/himalaya, propose drafts (never
    send unattended)
  - `task-capture` — friction-free add from chat or Signal into the task store
  - `quarterly-review` — assemble evidence into a draft report (docx skill if
    wanted)
- **Data:** plain markdown/JSON in a directory adam-local can read; rendered into
  the CIDER dashboard via regenerate_dashboard. No new database.
- **Nudges:** send_signal_alert for scheduled invitations, with a skip affordance.
- **Autonomy config:** a single `autonomy.yaml` with tiers:
  - read/summarize → autonomous
  - create drafts, tasks, calendar *proposals* → autonomous but flagged
  - send messages, accept invites, modify calendars → confirm required
  - delete anything → never autonomous

## Phases (GATE = show Adam, get sign-off before continuing)

**Phase 0 — Audit + public-repo hygiene. Zero functional changes. Do this FIRST.**

This repo is public and its history predates good secret discipline.

1. Confirm the working copy tracks github.com/adammoore/llm-pa; report the local
   path and remote URL.
2. Run a full-history secret scan (gitleaks or trufflehog) and report every hit.
3. Assume the following were exposed at some point and must be ROTATED regardless
   of scan results: Anthropic API key, Google OAuth client secret, app SECRET_KEY,
   TickTick client credentials. List them in the Phase 0 report; Adam rotates.
4. If a history rewrite is needed (git filter-repo / BFG), propose it at the
   GATE — it means a force-push, which is acceptable (solo repo) but must be
   deliberate; existing forks/clones will diverge.
5. Confirm `.gitignore` covers `.env`, `token.json`, `client_secret.json`, and
   private `data/` content before the first new commit.
6. Read the legacy repo. Produce `INVENTORY.md`: what exists, what's dead, what's
   worth keeping.
7. Extract to `/extracted`: the prompt bank (`prompt_system.py` SAMPLE_PROMPTS),
   the action-learning questions (from `DailyPrompt.js`), the category taxonomy.

**GATE.**

**Phase 1 — ADR.** Write `ADR-001` proposing the final shape, incorporating
answers to the Open Decisions below and the `legacy/`-vs-delete choice from Repo
strategy. Two pages max. **GATE.**

**Phase 2 — Build.** Implement skills one at a time; demo each before starting the
next. Wire data into the dashboard as you go.

**Phase 3 — Schedules & nudges.** launchd jobs for daily/weekly/monthly cadences;
Signal invitations that can be skipped in one tap.

**Phase 4 — Decommission.**
- Verify the `v1-legacy` tag and `archive/2024-fastapi-react` branch exist and
  push both.
- Remove or relocate legacy code on main per the Phase 1 decision.
- Rewrite README: what this is now, one-command start, link to the legacy tag.
- Final CHANGELOG entry summarizing the migration.

## Open decisions — ask Adam before Phase 1

1. Task store: local files (recommended) vs Apple Reminders sync vs TickTick
   revival.
2. Any web UI at all, or CIDER-dashboard-only? (Recommended: dashboard-only.)
3. iMessage: read local chat.db on macOS? Requires Full Disk Access and explicit
   consent.
4. Account scoping for comms triage: which gog/Gmail accounts are in scope, and
   any boundaries to maintain between them.
5. Nudge behavior: Signal only, or also calendar-event reminders?

## Working agreements

- Small, frequent commits with conventional messages. Maintain `CHANGELOG.md`
  (successor to the old updates.txt habit).
- Python: PEP8, type hints, docstrings, ruff clean. Shell: shellcheck clean.
- Never commit secrets; env/keychain only.
- Ask before adding any new external service, credential, or anything that sends
  messages.
- Don't run ahead of a GATE. A question costs seconds; unpicking costs evenings.

## Definition of done

- Daily/weekly/monthly check-ins fire on schedule, log to daily notes, nudge via
  Signal, and are skippable in one tap.
- Morning output includes calendar and inbox summaries for the in-scope accounts.
- `quarterly-review` produces a usable draft from real activity on demand.
- `autonomy.yaml` is enforced and documented.
- Legacy app archived with a clear README trail, secrets rotated, history clean.

## Kickoff (for Adam, not Claude Code)

```
cd /path/to/llm-pa   # confirm this clone tracks github.com/adammoore/llm-pa
claude
> Read OVERHAUL_BRIEF.md in full, confirm the remote, then run Phase 0 only.
> Stop at the GATE with INVENTORY.md, /extracted, and the secret-scan report.
```
