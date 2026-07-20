# Sources & integrations roadmap (post-v2.0.0)

The core overhaul (Phases 0–4) is **complete** at `v2.0.0`: 7 skills, dashboard, launchd
schedules, autonomy tiers, legacy archived. This file tracks the *source integrations* added
by request after launch, and who does what.

## Principles for new sources

- **Sanctioned clients first, scraping last.** Prefer official apps / APIs / local sync over
  browser automation. Automation only where nothing else works.
- **Employer systems:** Adam has confirmed he accepts the risk of accessing his own work data.
  The assistant will still **never** enter corporate credentials/MFA or bypass bot-detection,
  and prefers official Microsoft/Slack clients. Adam owns the acceptable-use call.
- **PA / legal separation holds.** Even where the PA can read sensitive stores (e.g. all of
  Apple Notes, per Adam's instruction), it must not surface case/safeguarding/medical content
  into the dashboard, nudges, or any PA output. Lists and logistics only.

## Sources

| Source | Method | Status | Whose action |
|--------|--------|--------|--------------|
| Gmail ×2 (personal, fairres) | gog / himalaya | ✅ live | — |
| Google Calendar ×2 | gog | ✅ live | — |
| Local task store | lib/taskstore | ✅ live | — |
| **Apple Notes (all notes)** | AppleScript: read all, capture into PA-owned `PA Inbox` note | ✅ built | — |
| **Signal nudges → phone** | openclaw message send (wired) | ⏳ blocked | Adam: register signal-cli + run :8080 daemon (SIGNAL_SETUP.md) |
| **iPhone two-way (inbound)** | `openclaw agents add/bind` → PA repo workspace | ⏳ after Signal | assistant, once Signal up |
| **Work OneDrive / SharePoint** | official OneDrive.app sync → PA reads local files | ✅ reader built (metadata-only) | — (signed in, syncing) |
| **Work Outlook (mail/cal)** | IMAP via himalaya, or ICS calendar publish, if tenant allows; else browser | 🔜 TBD | Adam: check what tenant permits |
| **Work Teams** | sanctioned client / browser (fragile) | 🔜 later | TBD |
| **Slack (notch8.slack.com)** | no MCP available — per-user token/app or browser automation | 🔜 TBD | Adam: create a Slack user token, or approve browser path |

## Sequence

1. **Apple Notes** — buildable now (read-all + capture); needs the capture-target note name.
2. **Signal daemon** (Adam) → then wire **iPhone inbound routing** (assistant).
3. **OneDrive reader** — after Adam signs the work account into OneDrive.app and syncs a folder.
4. **Slack (notch8)** — confirm token vs browser, then build.
5. **Outlook / Teams** — last; depends on what the tenant allows.
