# ReviewGuide.ai — Milestone Consolidation Brief (Pre-flight P1)

## Purpose

Produce the **single locked source of truth** the autonomous build crew will
work against. Until this milestone exists, the crew has nothing to be faithful
to and must not run.

## Why this is needed

ReviewGuide.ai is a brownfield, live-in-production AI shopping/travel assistant
(~85% built, deployed at reviewguide.ai). Its planning material is **four
overlapping, partially contradictory generations** that were never reconciled:

1. **Original "Phase 1" plan** (Nov 2025) — stale; that build finished long ago.
2. **Scratch docs** — `plan.md`, `progress.md`, `research.md`, `discovery.md` —
   explicitly `.gitignore`d, NOT canonical.
3. **GSD `.planning/` v2.0 milestone** (Mar–Apr 2026) — closed / complete.
4. **Audit + handoff docs** (Apr–May 2026) — the only CURRENT material.

Contradictions across them: MCP tool count is given as 17 / 19 / 22 / 23; the
"current branch" as `frontend-redesign` / `v2-with-swipe` / `main`. An
autonomous crew pointed at this would build against an incoherent spec.

## The ONLY authoritative inputs — consolidate from these, trust nothing else

- `docs/audits/opus-4.7-audit-report-2026-04-16.md`
- `docs/audits/qa-report-2026-04-21.md`
- `docs/audits/next-session-prompt-2026-05-19.md` — **most current**; it
  explicitly supersedes `next-session-prompt-2026-04-22.md` (do NOT use that).
- `.planning/codebase/CONCERNS.md` — the 20-item tech-debt matrix; pull the
  **5 Critical + 8 High** items.

## Archive (de-canonicalize — keep history, don't delete)

Move to an `archive/` folder or clearly mark non-canonical:
- `PHASE_1_DEVELOPMENT_PLAN.md`, `COMPLETED_FEATURES.md`, `REMAINING_TASKS.md`,
  `ARCHITECTURE_DIAGRAM.md`, `DETAILED_FLOW_DIAGRAM.md`,
  `ReviewGuide_Complete_Development_Plan.docx`
- `plan.md`, `progress.md`, `research.md`, `discovery.md` — already gitignored;
  leave them but do not treat as canonical.
- The closed v2.0 `.planning/` milestone (phases 12–16) — leave as history.

## The task

Run `/gsd:new-milestone` to create ONE fresh, dated, locked milestone:

> **Milestone 1 — "Production Stabilization"**
> **Scope** = the 5-fix punch-list from `next-session-prompt-2026-05-19.md`
> **plus** the 5 Critical and 8 High items from `CONCERNS.md`.
> **Priority 1** = the affiliate-link accuracy bug (the positional-zip
> mismatch that sends users to wrong / cheaper products). This is an
> **FTC / Amazon-ToS compliance risk** — it is fixed first.
> **Out of scope** = v4.0 features — parked as Milestone 2 (scope TBD with
> Mike, the business owner who holds the affiliate credentials).

Reconcile every contradiction so the locked spec has **zero ambiguity** — state
the real MCP tool count and the real production branch explicitly. The
milestone's `REQUIREMENTS.md` + phase breakdown become the crew's source of
truth.

## Human decisions to lock during this step (pre-flight P2–P4)

- **P2 — Canonical branch.** `main` vs `v2-with-swipe` vs
  `v3-full-implementation`. Production (`v2-with-swipe`) is ~96 commits behind
  `v3-full-implementation`, and those commits are mostly bug fixes. Decide the
  real production branch, land the fixes, and declare **one production branch**
  + **one integration branch**. Record both in the milestone.
- **P3 — Secrets.** Rotate the live tokens in `.mcp.json`, `1.py`, `.env`
  before the crew clones (each crew workspace carries the tree).
- **P4 — Cleanup.** Pin the working tree to ONE absolute path (3+ copies exist
  in `downloads/`). Delete the empty `NUL` file. Decide `kishan_frontend/`'s
  fate.

## Definition of done

- One locked, dated `.planning/` milestone exists with unambiguous scope.
- Stale planning generations archived / clearly marked non-canonical.
- Canonical production + integration branches declared and recorded.
- Secrets rotated; working path pinned; `NUL` and duplicate copies resolved.

When all of the above are true → the crew can launch (see `crew/AGENT-PROMPTS.md`).
