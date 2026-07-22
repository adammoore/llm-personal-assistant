# ADR-004 — A People Layer (Monica) + a Spatial-Encoding Layout

- **Status:** Proposed (assessment — awaiting direction)
- **Date:** 2026-07-22
- **Extends:** ADR-003 (ZigZag facets), DESIGN.md (ADHD/ND UX)

Two connected asks: add a **people/relationship dimension** (assess Monica CRM), and make the
**layout represent need / urgency / context** rather than a flat grid (spatial hypertext).

---

## Part A — People layer (Monica CRM assessment)

**What Monica is.** Open-source (AGPL-v3), self-hosted personal CRM. Rich contact profiles
(relationship type, "how we met", birthday/anniversary), auto reminders, relationships
*between* contacts, conversation/activity logging, per-contact tasks. Has a **REST API**
(`/api/contacts`), CSV import, Docker self-host. ([itsfoss](https://itsfoss.com/monica/),
[GitHub](https://github.com/Monica-CRM/))

**Why it matters here.** The PA has **no people dimension** — people only appear implicitly
(mail senders, meeting attendees). Yet "person" is a first-class **ZigZag axis**: *follow
Jenny Evans across her mail + meetings + tasks*. That thread is currently impossible.

**Three ways to get it (fit vs. the PA's local, no-server, agent-native ethos):**

| Option | What | Fit |
|--------|------|-----|
| **A1. Light local people layer** *(recommended first)* | `data/people.json` — name, relationship, how-met, key dates, last-contact, notes, linked themes — read/written by the PA; a **People** card/facet (birthdays due, "haven't spoken to X in N weeks", person-as-a-thread). CSV-importable from Monica. | ✅ consistent with local-file store; no server; adds the dimension natively |
| **A2. Self-host Monica + API** | Run Monica (Docker/MySQL); PA reads contacts/reminders/relationships via its REST API. | ⚠️ reintroduces a server+DB (a sanctioned self-hosted app like OneDrive/OpenClaw, not the *PA's* server) — worth it only if you want Monica's full depth (gifts, debts, journal, conversation logs) and will maintain it |
| **A3. Hybrid** | Build A1 now; if you later run Monica, sync from its API into `people.json`. | ✅ best of both |

**Recommendation:** **A1 now** (the *person-as-a-ZigZag-dimension* is the real prize, and a
local file delivers it without a Laravel/MySQL stack), with A3 as the door to full Monica if
you decide you want it. The PA already has the sources to *populate* it (mail senders,
attendees) and to *use* it (surface a person's whole thread; nudge on birthdays / go-quiet).

---

## Part B — Spatial-encoding layout (spatial hypertext)

**The literature.** Shipman & Marshall's **VIKI / VKB** show meaning expressed through
**visual similarity and co-location** — categories and relationships *emerge* from position,
proximity and visual attributes rather than explicit links; a **spatial parser** detects the
implicit structure people create and *surfaces* it without rearranging their layout; and
**incremental formalization** avoids the cognitive cost of forcing structure too early.
([VKB](https://people.engr.tamu.edu/shipman/vkb/www2000.htm),
[VIKI](https://www.semanticscholar.org/paper/76dba0d2a151e248c33c54a94b64d7157932df0e),
[implicit structure](https://www.semanticscholar.org/paper/2ce7ba29936f1ab74a4f0beb320085f5873c591d))

**The gap you named.** Our grid is *arbitrary* — an overdue high-priority task looks identical
to a someday-maybe one; context is only a colour dot; nothing about **position or size**
conveys need or urgency. Spatially, the layout says nothing.

**The tension (and the resolution).** Pure spatial hypertext is a free 2-D canvas — which
collides with the ADHD/ND evidence for **predictability and low clutter** (DESIGN.md). So the
synthesis is **spatial *encoding* within a predictable, deterministic arrangement** — the
map's axes are fixed and learnable; only *where an item lands on them* varies. Encode:

- **Urgency → vertical position** *(the strongest lever)*: a **Now → Next → Soon → Someday**
  gradient. Overdue/today rise to the top; undated sink. (Time-blindness: "what's now/next".)
- **Need/importance → size & weight**: high-priority items render larger/bolder; low-energy
  quick-wins get a distinct light treatment. Size = importance is glanceable.
- **Context → region + the existing colour**: contexts as consistent columns/bands (personal ·
  work · case), so an item's *place* and *hue* both say its context.
- **Proximity → relatedness**: same-theme items cluster (the ZigZag thread, made spatial).
- **Emergent structure (later)**: a VKB-style "these 6 are all Enact — group them?" suggestion
  — spatial parsing as an *offer*, never an auto-rearrange.
- **Incremental formalization**: keep capture frictionless; let theme/priority/steps accrete
  over time (the PA already does this — don't demand structure up front).

**Concrete first cut:** replace the fixed Tasks grid with an **urgency gradient** (Now/Next/
Soon/Someday bands), size tasks by priority, and lay contexts as columns/bands — a predictable
map where **height = urgency, size = need, column/colour = context**. Facets still pivot it.

---

## Recommendation / phasing

1. **Spatial layout first** (Part B first cut) — directly answers "not representative of need/
   urgency/context", pure local build, no new services, high daily value.
2. **A1 people layer** — adds the person dimension + facet; local file; medium build.
3. **A3 / Monica API** — only if you choose to self-host Monica for its full depth.

Open question (from DESIGN.md): a spatial/emergent layout trades *expressiveness* against
*predictability* — so ship it **theme-toggle-style** (keep the current grid available) and see
which you actually prefer, rather than replacing the grid outright.
