# PA design principles — ADHD / neurodivergent-first

Evidence-based UX principles for this PA, from a deep-research pass (2026-07-21; 27 sources,
25 claims adversarially verified, 23 confirmed). Confidence is flagged per principle. Two
claims were **refuted** and are deliberately *not* used (see end). Ted Nelson's *intertwingled*
/ZigZag and the *Context Rover* (energy/impulse/focus) are **design lenses layered on the
evidence**, not themselves evidenced — used where compatible.

> Overriding finding: **externalise working memory.** WM deficits are *primary* in ADHD and
> causally drive impulse/inhibition failure (Frontiers in Psychiatry 2024, N=110, controlled),
> so memory support, source aggregation, task decomposition, and always-visible "now/next"
> are **core infrastructure, not features**.

## Principles → how this PA applies them

1. **Aggregate, don't make me remember** *(high)*. One unified stream over tasks / calendar /
   mail / work; persist state visibly; prompt, never rely on recall. Self-made reminders go
   invisible within days. → `lib/activity.unified()`, the dashboard, PA Today/Inbox notes.
   *Do:* a "where was I" recent-activity view. *Don't:* bury state a page away.

2. **Surface the next physical step** *(high)*. Task-initiation paralysis is the dominant
   barrier; decomposition into small subtasks reduces it. → ✨ Magic ToDo. *Do:* show the
   **first step as the next action** at the point of action. *Don't:* present the whole goal.

3. **Chunk + progressive disclosure** *(high)*. Small chunks, short lines (≤4), key-point
   summaries, single-focus low-clutter, collapse/expand, defaults that hide non-essentials.
   → collapsible cards, "+N more", the ✨ inbox summary.

4. **Typography & colour** *(high)*. Sans-serif **≥16px, 1.5 line-height**, **bold key items**
   (dates/deadlines), left-aligned, simple colours, generous white space. *Avoid* bright/
   clashing colours, all-caps runs, italics/underline for emphasis, justified text, and
   **high-saturation red for urgency** — convey urgency by **position + label + a muted
   accent**, not alarm-red. Individual variation is large → **user-adjustable text size &
   theme** beats any fixed palette.

5. **No motion** *(high)*. Irrelevant animation raises cognitive load and distraction
   (esp. autistic users), who then change behaviour to avoid it. *Do:* respect
   `prefers-reduced-motion`, keep transitions minimal, avoid jarring auto-refresh. *Don't:*
   auto-play or move things.

6. **Make time visible; rhythm not grid** *(medium)*. A clear **now / next** strip and
   deadlines; time as flexible rhythm, optionally "ideal vs baseline" — not a rigid hour grid.
   → stat-bar "next", due chips.

7. **Invitation, not command (PDA-aware)** *(medium)*. "Want to look at today?" not "Do X
   now." Gentle nudges over guilt; reward without manipulation. → all nudges + framing.

8. **Body-doubling / focus sessions** *(medium)*. Optional shared/companion focus sessions
   help completion & sustained attention (small VR n=12; treat as promising). → a future
   focus-session mode. *Note:* "ambient affirmation" presence was **refuted** — don't build it.

9. **Faceting (ZigZag), done safely** *(medium/derived)*. Keep the multi-dimensional
   connectivity in the **data model**; render each pivot as a **chunked, single-focus,
   progressively-disclosed** view. Open only a few facets by default; keep them predictable and
   consistent (autistic users favour predictability). *Don't:* a dense all-at-once N-dimensional
   display. → the planned facet bar (context / source / theme), one pivot at a time.

## Context Rover mapping (a lens, not evidence)
Energy / impulse / focus-session state maps onto our `energy` task field + `focus` view +
(future) focus sessions. Open question the corpus couldn't answer: whether energy-matched
surfacing measurably helps — so offer it, don't force it.

## Refuted — do NOT implement
- "Limit the number of buttons / make all content static." (0-3) — the button-limiting
  rationale did not survive verification.
- "Ambient digital body-doubling with light affirmations reduces initiation friction." (0-3).

## Key sources
Frontiers in Psychiatry 2024 (WM→inhibition, N=110); arXiv 2602.09381 & 2603.17258 (ADHD
task-management co-design); arXiv 2211.11993 (animation harm, ENASE 2022); UK Home Office /
GOV.UK accessibility posters; NHS West Yorkshire neurodivergence guide; British Dyslexia
Association; NN/g Filters vs Facets; Nelson *Intertwingularity* / ZigZag.
