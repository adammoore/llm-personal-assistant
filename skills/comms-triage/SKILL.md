---
name: comms-triage
description: Summarise both Gmail inboxes and propose draft replies. Use when Adam wants to deal with email / "do my inbox" / "any replies needed", or after a check-in. Reads bodies only for items Adam acts on; writes drafts locally; saves to the mailbox only on confirmation. Never sends.
---

# comms-triage

Turn two noisy inboxes into a short, per-account picture of what actually needs Adam, and
have draft replies ready — without sending anything.

## Autonomy (ADR-001 §7 / autonomy.yaml)

- Listing + summarising (`triage.py`, reading a chosen body) → **autonomous** (read-only).
- Writing a proposed draft to `data/drafts/` → **autonomous-but-flagged** (`propose_draft`).
- Saving a draft into the live Gmail Drafts folder → **confirm_required** (`save_gmail_draft`).
- **Sending is out of scope for this skill. Never `himalaya message send`.**

## Flow

1. **Shortlist** (deterministic):
   ```bash
   python3 skills/comms-triage/triage.py --per-account 10
   ```
   Prints a per-account shortlist; each line carries an actionable id, e.g.
   `` `[fairres #1721]` **Henry Williams** — Private and Confidential ``.
   Accounts are separate and must stay separate.

2. **Prioritise with judgement.** From each account's shortlist, lift what genuinely needs
   Adam — real people, replies to him, institutions/solicitors — and demote marketing that
   slipped the noise filter. Present per account as: **needs a reply**, **worth knowing**,
   and a one-line "rest is noise". Keep it to a glance.

3. **Read only what Adam wants to act on.** For a chosen item:
   ```bash
   himalaya message read <id> -a <mail-account>   # e.g. -a fairresconman
   ```
   Summarise the ask in a sentence.

4. **Propose a draft** (never send). Write it to
   `data/drafts/<account>/<id>.md` with the intended To/Subject and body. Match Adam's
   voice: plain, warm, brief. For anything touching the legal matters, keep it factual and
   procedural (BIFF: brief, informative, friendly, firm) and **do not invent facts** — if a
   reply needs case detail, flag that it belongs to the relevant track, don't fabricate it.
   Show the draft in chat for review.

5. **Only on Adam's explicit yes**, save it into the mailbox as a *draft* (not sent):
   ```bash
   himalaya message save Drafts -a <mail-account> < data/drafts/<account>/<id>.md
   ```
   (raw RFC822: `To:`, `Subject:`, blank line, body). Confirm it's saved as a draft to
   finish and edit/send by hand. If Adam doesn't confirm, the draft just stays local.

## Guardrails

- **Never blend the two accounts.** A reply is drafted from, and about, one account only.
- **Never send**, accept invites, or set up rules/forwarding here.
- The PA stays separate from CIDER: surface legal mail and draft *procedural* replies if
  asked, but substantive legal content lives in the case tracks, not in PA drafts.
- If a draft would commit Adam to anything (money, dates, admissions), stop and ask rather
  than drafting it speculatively.
