---
name: work-pull
description: Read Adam's Westminster/Enact work comms on-demand — Outlook mail + calendar, Teams, Slack (Notch8) — from his already-open, logged-in dedicated Chrome. Use when he asks about work mail/calendar/Teams/Slack ("check my Westminster inbox", "what's on my work calendar", "any Teams/Slack I've missed"). Read-only; on-demand (not the always-on monitor).
---

# work-pull

Adam's institutional M365 has no API access, but his `Start Enact Role Dashboard.command`
launches a dedicated Chrome profile with remote debugging on `127.0.0.1:9222`, logged in and
pre-opened to Outlook, Teams, and Slack. This reads the **visible text** of those tabs over
CDP — no credentials, no login scraping, no continuous session.

## Autonomy & boundaries

- Read-only: it evaluates JS to pull visible text. It **never** clicks, sends, or navigates.
- **Only the four work surfaces** (Outlook mail, Outlook calendar, Teams, Slack) are read —
  by fixed URL match. It does not touch any other tab in that Chrome profile.
- **On-demand only.** A live browser session can't be a headless daemon, so this is not part
  of the always-on monitor — Adam triggers it.

## How to run

```bash
python3 skills/work-pull/pull.py                 # all four surfaces
python3 skills/work-pull/pull.py --source mail   # just Outlook mail (or calendar/teams/slack)
```

If it reports the Enact Chrome isn't running, ask Adam to launch
`~/Desktop/Start Enact Role Dashboard.command`, then retry.

## Flow

1. Run `pull.py` (optionally `--source`).
2. Summarise per surface with judgement: for **mail**, lift who needs a reply (real people,
   e.g. Jenny Evans / Notch8) and the ask, demote noise; for **calendar**, today/tomorrow's
   work meetings; for **Teams/Slack**, unread threads that mention Adam or need action.
3. Keep it a glance, per surface, labelled. The tab text is best-effort (web-app DOM), so read
   for meaning, not exact structure.
4. If Adam wants to act (reply, post), draft it for him but **do not send** — surface it and
   let him send in the browser himself.

## Notes

- Westminster documents already sync locally via OneDrive (`lib/onedrive.py`); this covers the
  *comms* half (mail/calendar/Teams/Slack).
- This is the same repo/PA — surface it in a work-labelled section; keep it distinct from the
  personal Gmail accounts.
