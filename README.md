# ReviewGuide

A conversational AI advisor for purchase decisions.

ReviewGuide helps you decide what to buy through a real two-way dialogue —
asking clarifying questions when needed, returning a synthesized editorial
recommendation with a ranked product carousel, and continuing to refine as
the conversation develops. It is built around a deliberate voice:
knowledgeable, curious, opinionated about fit, and constitutionally
incapable of blowing smoke. No glazing. No hedging. A clear pick with a
clear reason.

**Who it's for:** people making considered or aspirational purchases —
headphones, laptops, hotels, anything where the choice deserves thought.
The AI calibrates to your depth and priorities over time.

---

## Canonical product docs

These are the sources of truth for the product. Read them before making
any code, design, or scope decision — and read tone.md first, before the
others.

| Doc | Purpose |
|-----|---------|
| [`tone.md`](tone.md) | Voice and personality — source of truth for every string, prompt, and microcopy decision. Banned-phrases blocklist is non-negotiable. |
| [`reviewguide-spec.md`](reviewguide-spec.md) | Mobile-first conversational design spec — screens, components, interactions, visual guardrails. |
| [`FRONTEND_AGENT_CONTEXT.md`](FRONTEND_AGENT_CONTEXT.md) | Brief for frontend/design work — component status, file map, done criteria. |
| [`BACKEND_AGENT_CONTEXT.md`](BACKEND_AGENT_CONTEXT.md) | Brief for backend/AI orchestration — pipeline, output schema, personality profile system. |
| [`RECONCILIATION.md`](RECONCILIATION.md) | Codebase audit against the spec — aligned, needs change, missing, out of scope. |

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS |
| Backend | FastAPI (Python), LangGraph |
| AI | Claude (Anthropic SDK) |
| Database | PostgreSQL 15 |
| Cache / Personalization | Redis 7 (per-session profile cache) |
| Deploy | Vercel (frontend) + Railway (backend + DB) |

See [`CLAUDE.md`](CLAUDE.md) for local dev setup, Docker commands, and
troubleshooting.

---

## Current direction

The product is a **mobile-first conversational advisor**. See
[`reviewguide-spec.md`](reviewguide-spec.md) and the agent context docs for
current scope and design decisions.

Active development happens in milestones tracked through the agent context
docs. Documents in `archive/` are legacy — do not act on them without
explicit instruction.
