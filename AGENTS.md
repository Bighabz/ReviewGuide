# ReviewGuide.ai - Development Notes

## Quick Start

```bash
# Start backend services (postgres, redis, backend)
docker-compose up -d

# Start frontend dev server
cd frontend && npm run dev
```

## Architecture Overview

### System Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind | User interface |
| Backend | FastAPI (Python), LangGraph | API and AI orchestration |
| Database | PostgreSQL 15, SQLAlchemy async | Data persistence |
| Cache | Redis 7 | Sessions, search cache, state storage |
| AI | OpenAI GPT-4o, Perplexity | LLM and search |
| Observability | Langfuse | Tracing and monitoring |

### LangGraph Workflow

The chat system uses a state machine (`backend/app/services/langgraph/workflow.py`):

```
User Message
     │
     ▼
┌─────────────┐
│ Safety Agent │ ─── Content moderation, PII detection
└─────────────┘
     │
     ▼
┌─────────────┐
│ Intent Agent │ ─── Classify: intro, product, travel, general
└─────────────┘
     │
     ▼
┌───────────────┐
│ Clarifier Agent│ ─── Collect missing information (halts if needed)
└───────────────┘
     │
     ▼
┌────────────────┐
│ Domain Executor │ ─── Product search, travel planning, etc.
└────────────────┘
     │
     ▼
Response to User
```

### MCP Server

17 tools exposed via Model Context Protocol (`backend/mcp_server/main.py`):

- **Product tools (7):** search, evidence, affiliate, ranking, normalize, compose, comparison
- **Travel tools (5):** itinerary, search_hotels, search_flights, destination_facts, compose
- **Utility tools (5):** general_search, general_compose, intro_compose, unclear_compose, next_step_suggestion

### State Management

- **GraphState** TypedDict flows through all agents
- **HaltStateManager** persists partial state to Redis when awaiting user input
- **ChatHistoryManager** handles conversation persistence to PostgreSQL

## Important Configuration

### CORS Settings
**Location:** `docker-compose.yml` line ~60

```yaml
CORS_ORIGINS: '["http://localhost:3000","http://localhost:3001","http://localhost:3002","http://localhost:3003","http://127.0.0.1:3000","http://127.0.0.1:3001"]'
```

**If frontend runs on a different port**, you MUST:
1. Update `CORS_ORIGINS` in `docker-compose.yml`
2. Restart backend: `docker-compose up -d backend`

### Port Usage
- **Frontend:** 3000 (auto-increments if busy)
- **Backend API:** 8000
- **PostgreSQL:** 5432
- **Redis:** 6379

### Environment Variables

Key variables in `backend/.env`:

| Variable | Required | Purpose |
|----------|----------|---------|
| `SECRET_KEY` | Yes | JWT signing (min 32 chars) |
| `OPENAI_API_KEY` | Yes | LLM calls |
| `DATABASE_URL` | Yes | PostgreSQL connection |
| `SEARCH_PROVIDER` | No | "openai" or "perplexity" |
| `RATE_LIMIT_ENABLED` | No | Enable rate limiting |

## Development Workflows

### Adding a New MCP Tool

1. Create tool file: `backend/mcp_server/tools/your_tool.py`
2. Follow pattern from existing tools:
   ```python
   async def your_tool(state: dict) -> dict:
       # Read from state
       user_message = state.get("user_message", "")

       # Do work
       result = await some_operation()

       # Return state updates
       return {"your_key": result}
   ```
3. Register in `backend/mcp_server/main.py`:
   - Add import
   - Add to `@app.list_tools()`
   - Add to `@app.call_tool()` router

### Adding a New API Endpoint

1. Add route in `backend/app/api/v1/your_route.py`
2. Use Pydantic models for request/response
3. Add rate limiting: `Depends(check_rate_limit)`
4. Register in `backend/app/main.py`

### Adding a Frontend Component

1. Create in `frontend/components/`
2. Use TypeScript with proper interfaces
3. Avoid `Math.random()` in SSR (causes hydration errors)
4. Follow existing patterns (Tailwind, lucide-react icons)

## Troubleshooting

### Chat not responding / CORS errors

1. Check browser console for CORS errors
2. Verify frontend port matches `CORS_ORIGINS` in docker-compose.yml
3. Test CORS preflight:
   ```bash
   curl -X OPTIONS "http://localhost:8000/v1/chat/stream" \
     -H "Origin: http://localhost:3001" \
     -H "Access-Control-Request-Method: POST"
   ```
   Should return `200 OK`

### Hydration errors (server/client mismatch)

- Don't use `Math.random()` in components rendered on server
- Use deterministic values based on IDs instead
- Check for `Date.now()` or `new Date()` in SSR

### Changes not showing after edit

```bash
# Windows
taskkill //F //IM node.exe

# Then
rm -rf frontend/.next
cd frontend && npm run dev
```

### Backend not starting

```bash
# Check logs
docker-compose logs backend --tail=100

# Verify env vars
docker-compose config

# Rebuild
docker-compose build backend
docker-compose up -d backend
```

### Database issues

```bash
# Run migrations
docker-compose run --rm migrations

# Or manually
cd backend && alembic upgrade head

# Check connection
docker-compose exec postgres psql -U postgres -d reviewguide_db
```

### Redis connection failed

```bash
# Check Redis is running
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping
```

## Key Files Reference

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Docker services, **CORS settings** |
| `backend/app/core/config.py` | Backend settings (300+ options) |
| `backend/app/services/langgraph/workflow.py` | LangGraph state machine |
| `backend/mcp_server/main.py` | MCP server with 17 tools |
| `backend/tests/conftest.py` | Test fixtures and mocks |
| `frontend/lib/chatApi.ts` | API client with SSE streaming |
| `frontend/components/ChatContainer.tsx` | Main chat UI |
| `frontend/app/chat/page.tsx` | Chat page, URL params |

## Features

### Sticky Chat Bar (Browse -> Chat)
- User types query in SearchInput on `/browse`
- Navigates to `/chat?q=<query>&new=1`
- ChatContainer processes `initialQuery` prop and auto-sends to API

### Streaming Architecture
- Backend uses `graph.astream_events()` for real-time updates
- `stream_chunk_data` in GraphState enables mid-workflow streaming
- Frontend handles SSE with reconnection logic

### Halt State (Multi-turn Conversations)
- When clarification needed, workflow halts
- State saved to Redis via `HaltStateManager`
- User response resumes from saved state

### New Chat / History Buttons
- Always visible in UnifiedTopbar (not just on /chat route)
- Handlers passed from parent components or use router fallback

## Custom Skills

Use these slash commands for common workflows:

| Command | Purpose |
|---------|---------|
| `/feature-dev` | Multi-phase feature development |
| `/review` | Code review checklist |
| `/test` | Run and analyze tests |
| `/deploy` | Deployment checklist |

## Component Map (read before editing UI — there are duplicates!)

This codebase has **multiple components for the same concept**. Editing the wrong one is the #1 time-sink. Go to the right file:

### Product cards (THREE of them, by render context)
- **In chat results** → rendered by `components/blocks/BlockRegistry.tsx`:
  - `products` / `carousel` blocks → **`components/ProductCarousel.tsx`** (the main shortlist carousel)
  - `product_review` block → **`components/ProductReview.tsx`** (rich review card: image-left, pros/cons, "Where to buy")
  - `inline_product_card` → `components/InlineProductCard.tsx`
- **`/results/[id]` summary page only** → **`components/ResultsProductCard.tsx`** (NOT used in chat — don't confuse with the above)
- Saved/Compare cards are inline in `app/saved/page.tsx` / `app/compare/page.tsx`.
- The shared bookmark store is `lib/savedItems.ts` (`SaveToggle` is duplicated inline in ProductCarousel + ProductReview + ResultsProductCard).

### Logos (THREE)
- **`components/Brand.tsx`** — `Wordmark`/`WordmarkStatic`/`LogoHero`/`HeaderBrand`/`TransitionalBubble` (code-based terracotta; `Wordmark` is in the topbar/header). `LogoHero` is now unused on Discover but still exported.
- **`components/AnimatedLogo.tsx`** — plays the recolored `/images/animated_logo.mp4`; used on **`/login` only**.
- **`components/DiscoverHeroLogo.tsx`** — autoplays the recolored video on the Discover hero (`app/page.tsx`), with a static-PNG reduced-motion fallback.

### Routes / screens
- **Discover = `app/page.tsx`** (served at `/`). `/discover` and `/browse` just **redirect to `/`**.
- Chat = `app/chat/page.tsx` → `components/ChatContainer.tsx` (welcome/empty state lives here) → `components/Message.tsx` (bubbles, blog card, clarifier chips, follow-up Q).
- Headers: desktop `components/UnifiedTopbar.tsx`, mobile `components/MobileHeader.tsx` + `components/MobileTabBar.tsx` (bottom tabs; 5th tab labelled "You").

### Design tokens (terracotta-on-cream, NO blue)
- `app/globals.css` `:root` CSS vars + `app/tailwind.config.ts`. Key: `--terra #B8543A` (primary, replaced old `#1B4DFF`), `--ink #1A1816`, `--paper #FAFAF7`, `--line #E8E6E1`. Fonts: DM Sans (UI), Newsreader (`font-serif`, body), Instrument Serif (`.rg-display`, italic display). `rg-*` utility classes (eyebrow, hairline, breath, etc.) live in globals.css.
- The blueprint spec is `frontend/design/DESIGN.md`; gap analysis `frontend/design/GAP_ANALYSIS.md`.

### Backend field passthrough (the silent-drop trap)
- A new field from a composer tool must be wired through **all 5 layers** or it's silently dropped: composer (`mcp_server/tools/*`) → validator (`app/services/tool_validator.py`, the Pydantic schema) → `_extract_results` (`app/services/plan_executor.py`) → `plan_executor_node` (`app/services/langgraph/workflow.py`) → SSE (`app/api/v1/chat.py`). Mirror `follow_up_question` / `transitional_reasoning` / `affiliate_products` as the template.
