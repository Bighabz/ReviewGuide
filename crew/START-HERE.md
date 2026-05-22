# START HERE — ReviewGuide.ai Build-Crew Stand-Up

This folder stands up an autonomous build crew for ReviewGuide.ai, modeled on
the "Hermes" crew. **The crew cannot launch until pre-flight is done — that is
the first session's job.**

Order of use:
1. Paste the **STARTING PROMPT** below into a fresh Claude Code session opened
   in this repo. It runs pre-flight (P1–P4).
2. P1 executes `crew/MILESTONE-BRIEF.md` — consolidates the locked spec.
3. When pre-flight reports complete, launch the four agents from
   `crew/AGENT-PROMPTS.md`.

---

## STARTING PROMPT — paste into a Claude Code session in this repo

```
You are running PRE-FLIGHT to stand up an autonomous build crew for
ReviewGuide.ai — a brownfield, live-in-production AI shopping + travel
assistant (deployed at reviewguide.ai; Python/FastAPI + LangGraph backend,
Next.js 14 frontend, Postgres + Redis). The crew = four Discord agents
(forge / lens / scout / Foreman); their prompts are in crew/AGENT-PROMPTS.md.
They MUST NOT launch until pre-flight is complete.

Do pre-flight in order:

P1 — SOURCE OF TRUTH. Read crew/MILESTONE-BRIEF.md and execute it. The project
has FOUR overlapping, contradictory planning generations and no canonical
spec. Consolidate them into ONE locked .planning/ milestone via
/gsd:new-milestone, using ONLY the audit trio + CONCERNS.md as input. This
locked milestone becomes the crew's source of truth.

P2 — CANONICAL BRANCH. Resolve main vs v2-with-swipe vs v3-full-implementation.
Production (v2-with-swipe) is ~96 fix-commits behind v3-full-implementation.
Land the fixes, declare ONE production branch + ONE integration branch, and
record both in the milestone. STOP and ask the human for this decision.

P3 — SECRETS. .mcp.json, 1.py, and .env carry live tokens; each crew workspace
will clone the tree. STOP and ask the human to rotate the Supabase / GitHub /
Vercel tokens and scrub 1.py's hardcoded credentials — you cannot rotate them.

P4 — CLEANUP. Confirm this is the canonical repo path (there are 3+ duplicate
copies in downloads/ — the crew must be pinned to ONE). Delete the empty NUL
file. Ask the human what to do with kishan_frontend/ (a gitignored second
frontend copy — merge it into frontend/ or delete it).

RULES
- ReviewGuide.ai is a LIVE production app. Make NO application-code changes
  during pre-flight — pre-flight is spec consolidation, branch hygiene, and
  cleanup ONLY. The crew does the code work after launch, against the locked
  milestone.
- Where a step needs a human decision (P2, P3, kishan_frontend), STOP and ask.

When P1–P4 are all done, report "PRE-FLIGHT COMPLETE" and tell the human the
crew can launch using crew/AGENT-PROMPTS.md.
```

---

## After pre-flight

Launch the four agents from `crew/AGENT-PROMPTS.md` on a **separate Discord
server** ("ReviewGuide Build Crew"). Before launch, that file's header
preconditions must be true — branch protection on the production + integration
branches, and lens's own GitHub identity wired.

The crew pipeline: **scout diagnoses → forge builds → lens reviews → forge
merges to the integration branch → Foreman + Habib gate promotion to
production.**
