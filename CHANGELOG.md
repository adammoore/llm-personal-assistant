# Changelog

All notable changes to this project. Successor to the legacy `updates.txt` habit.
Format loosely follows Keep a Changelog; dates are absolute.

## [Unreleased] — agent-native overhaul

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
