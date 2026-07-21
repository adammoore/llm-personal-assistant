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
| **Signal nudges → phone** | openclaw message send → signal-cli daemon :8080 | ✅ LIVE (2026-07-20) | — (daemon launch agent installed) |
| **iPhone two-way (inbound)** | `openclaw agents add/bind` → PA repo workspace | ⏳ after Signal | assistant, once Signal up |
| **Work OneDrive / SharePoint** | official OneDrive.app sync → PA reads local files | ✅ reader built (metadata-only) | — (signed in, syncing) |
| **Work Outlook (mail/cal)** | CDP read of the logged-in Enact Chrome (`work-pull`) | ✅ on-demand | — |
| **Work Teams + Slack (Notch8)** | CDP read of the Enact Chrome (`work-pull`) | ✅ on-demand | — |


## Sequence

1. **Apple Notes** — buildable now (read-all + capture); needs the capture-target note name.
2. **Signal daemon** (Adam) → then wire **iPhone inbound routing** (assistant).
3. **OneDrive reader** — after Adam signs the work account into OneDrive.app and syncs a folder.
4. **Slack (notch8)** — confirm token vs browser, then build.
5. **Outlook / Teams** — last; depends on what the tenant allows.
