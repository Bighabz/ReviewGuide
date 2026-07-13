# 🎯 Remaining Tasks - Phase 1
## ReviewGuide.ai - What's Left to Complete

## 🚨 Critical Path (Must Complete)

### **Week 3 - UI Polish** (1 day remaining)

#### Day 21 (Nov 21) - UI Polish & Final Touches

- [ ] **Error States**
  - [ ] Error message component with retry button
  - [ ] Handle failed affiliate link generation
  - [ ] Handle failed travel API calls
  - [ ] Network error handling with user-friendly messages

- [ ] **Empty States**
  - [ ] "No messages yet" placeholder with example queries
  - [ ] "No products found" fallback message
  - [ ] "No hotels/flights available" fallback

---

#### Day 23 (Nov 23) - End-to-End Testing & Bug Triage
**Goal**: Manual testing of all user flows + bug prioritization

- [ ] **Manual Test Cases**
  - [ ] **Product Query Flow**
    - [ ] Type: "Best laptop for programming under $1200"
    - [ ] Verify: Product carousel appears with ≥3 items
    - [ ] Verify: Affiliate links work (eBay deeplinks)
    - [ ] Verify: Product images load
    - [ ] Verify: Prices display correctly
    - [ ] Click: "Buy Now" button opens eBay in new tab

  - [ ] **Travel Query Flow**
    - [ ] Type: "5-day trip to Tokyo in December for 2 adults"
    - [ ] Verify: Follow-up questions if dates missing
    - [ ] Verify: ≥5 hotel cards appear
    - [ ] Verify: ≥3 flight options appear
    - [ ] Verify: Day-by-day itinerary appears
    - [ ] Click: Hotel/flight deeplinks open in new tab

  - [ ] **Comparison Query Flow**
    - [ ] Type: "Compare iPhone 16 vs Samsung Galaxy S24"
    - [ ] Verify: Side-by-side comparison (if implemented)
    - [ ] Verify: Pros/cons for each product

  - [ ] **Multi-Turn Conversation Flow**
    - [ ] Type: "Tell me about Paris"
    - [ ] Type: "What's the weather like in summer?"
    - [ ] Verify: Context retained from previous message
    - [ ] Type: "Show me hotels there"
    - [ ] Verify: Correctly infers Paris as destination

  - [ ] **Slot Filling / HALT Flow**
    - [ ] Type: "Show me hotels"
    - [ ] Verify: Asks follow-up "Where would you like to go?"
    - [ ] Type: "New York"
    - [ ] Verify: Asks "When are you planning to travel?"
    - [ ] Type: "Next month"
    - [ ] Verify: Shows hotel results

- [ ] **Cross-Browser Testing**
  - [ ] Chrome (desktop)
  - [ ] Safari (desktop)
  - [ ] Firefox (desktop)
  - [ ] Mobile Safari (iOS)
  - [ ] Mobile Chrome (Android)

- [ ] **Performance Testing**
  - [ ] Install locust or similar load testing tool
  - [ ] Run 50 concurrent users simulation
  - [ ] Measure response times (p50, p95, p99)
  - [ ] Monitor server CPU/memory usage
  - [ ] Check for memory leaks

- [ ] **Bug Triage**
  - [ ] Create bug list with severity (P0, P1, P2, P3)
  - [ ] P0 (Critical): App crashes, data loss
  - [ ] P1 (High): Core features broken
  - [ ] P2 (Medium): UI issues, minor bugs
  - [ ] P3 (Low): Nice-to-have improvements
  - [ ] Fix all P0 and P1 bugs today

**Deliverable**: Bug report + all P0/P1 bugs fixed

---

#### Day 24 (Nov 24) - Performance Optimization
**Goal**: 20% improvement in latency + database optimization

- [ ] **API Optimization**

- [ ] **Frontend Optimization**

**Deliverable**: Performance report showing improvements

---

#### Day 25 (Nov 25) - Cost Controls & Rate Limiting
**Goal**: Keep cost per query <$0.05

- [ ] **Model Routing Strategy**
  - [ ] Configure model per agent in config:
    ```python
    SAFETY_MODEL = "gpt-4o-mini"
    INTENT_MODEL = "gpt-4o-mini"
    PLANNER_MODEL = "gpt-4o"
    CLARIFIER_MODEL = "gpt-4o-mini"
    PLAN_EXECUTOR_MODEL = "gpt-4o"  # for tool-using LLM calls
    ```
  - [ ] Update agent code to use configured models
  - [ ] Test with different model combinations

- [ ] **Token Budgets**
  - [ ] Implement token limits per agent:
    ```python
    TOKEN_BUDGETS = {
        "safety": 500,
        "intent": 1000,
        "planner": 3000,
        "clarifier": 1000,
        "plan_executor": 5000,
    }
    ```
  - [ ] Raise error if budget exceeded
  - [ ] Log budget usage to Langfuse

- [ ] **Enhanced Rate Limiting** (already exists, enhance)
  - [ ] Per-IP: 100 requests/hour (already done ✅)
  - [ ] Per-session: 20 requests/hour
  - [ ] External API limits:
    - [ ] Perplexity: 50 requests/hour
    - [ ] eBay: 100 requests/hour
    - [ ] Amadeus: Check API tier limits
  - [ ] Return clear rate limit errors to user

- [ ] **Circuit Breakers**
  - [ ] Install `circuitbreaker` library
  - [ ] Add circuit breaker for eBay API (fail fast after 5 errors)
  - [ ] Add circuit breaker for Amadeus API
  - [ ] Add circuit breaker for search APIs
  - [ ] Add circuit breaker for LLM calls
  - [ ] Graceful degradation messages

- [ ] **Cost Tracking Dashboard**
  - [ ] Query Langfuse API for cost data
  - [ ] Calculate cost per query (aggregate by session)
  - [ ] Calculate cost per agent
  - [ ] Create simple dashboard (can be terminal-based or Streamlit)
  - [ ] **Alert**: If any query costs >$0.10

**Deliverable**: Cost tracking dashboard + circuit breakers working

---

#### Day 26 (Nov 26) - Analytics & KPI Dashboard
**Goal**: Real-time metrics dashboard

- [ ] **Define Business Events** (already in events table, enhance tracking)
  - [ ] Ensure these events are logged:
    - [ ] `query_submitted`
    - [ ] `intent_classified`
    - [ ] `product_impression`
    - [ ] `affiliate_click`
    - [ ] `travel_impression`
    - [ ] `travel_click`
    - [ ] `conversation_completed`
    - [ ] `halt_triggered`
    - [ ] `cache_hit`
    - [ ] `cache_miss`
    - [ ] `error_occurred`

- [ ] **Create Streamlit Dashboard** (`metrics_dashboard.py`)
  - [ ] **Section 1: Request Volume**
    - [ ] Total requests (last 1 hour)
    - [ ] Total requests (last 24 hours)
    - [ ] Requests per minute (live chart)

  - [ ] **Section 2: Latency**
    - [ ] Line chart: p50, p95, p99 over last 24h
    - [ ] Color-code: green (<2s), yellow (2-4s), red (>4s)

  - [ ] **Section 3: Business Metrics**
    - [ ] Affiliate CTR (clicks / impressions)
    - [ ] Travel impressions (last 24h)
    - [ ] Travel CTR
    - [ ] Cost per query (average)

  - [ ] **Section 4: Cache Performance**
    - [ ] Cache hit rate (%)
    - [ ] Cache misses (count)
    - [ ] Top cached queries

  - [ ] **Section 5: Top Queries**
    - [ ] Most popular queries (last 24h)
    - [ ] Most expensive queries (by cost)

  - [ ] **Section 6: Error Rate**
    - [ ] Error count (last 24h)
    - [ ] Error rate (%)
    - [ ] Top errors by type

- [ ] **Setup Simple Alerting**
  - [ ] Email alert if error rate >5%
  - [ ] Email alert if p95 latency >5s
  - [ ] Email alert if cost per query >$0.10
  - [ ] Use SMTP or simple webhook (e.g., Discord, Slack)

- [ ] **Test Dashboard**
  - [ ] Run: `streamlit run metrics_dashboard.py`
  - [ ] Verify all charts render
  - [ ] Verify data updates in real-time

**Deliverable**: Working Streamlit dashboard

---

#### Day 27 (Nov 27) - Documentation
**Goal**: Complete technical documentation

- [ ] **Architecture Documentation** (`docs/ARCHITECTURE.md`)
  - [ ] System overview
  - [ ] Architecture diagram (Mermaid):
    ```
    User → FastAPI → LangGraph Workflow → 5 Agents → 19 MCP Tools → External APIs
    ```
  - [ ] Agent descriptions (Safety, Intent, Planner, Clarifier, Plan Executor)
  - [ ] MCP tool registry
  - [ ] State management (Blackboard Pattern)
  - [ ] Database schema
  - [ ] Technology stack

- [ ] **API Documentation** (OpenAPI/Swagger)
  - [ ] Verify `/docs` endpoint works
  - [ ] Add descriptions to all endpoints
  - [ ] Add request/response examples
  - [ ] Document authentication (JWT)
  - [ ] Document SSE streaming format

- [ ] **Agent Contracts** (`docs/AGENT_CONTRACTS.md`)
  - [ ] Document each agent's input/output
  - [ ] Example GraphState payloads
  - [ ] Error handling for each agent
  - [ ] Tool contract format

- [ ] **Database Schema** (`docs/DATABASE.md`)
  - [ ] ER diagram (Mermaid)
  - [ ] Table descriptions (9 tables)
  - [ ] Index strategy
  - [ ] Migration guide

- [ ] **Setup Guide** (`README.md` - update)
  - [ ] Prerequisites (Python 3.11+, Node.js, PostgreSQL, Redis)
  - [ ] Quick start:
    ```bash
    # Backend
    cd backend
    cp .env.example .env  # Configure env vars
    pip install -r requirements.txt
    ./setup_db.sh
    ./run.sh

    # Frontend
    cd frontend
    npm install
    npm run dev
    ```
  - [ ] Configuration (environment variables)
  - [ ] API keys required (eBay, Amadeus, OpenAI, etc.)
  - [ ] Troubleshooting common issues

- [ ] **Runbook** (`docs/RUNBOOK.md`)
  - [ ] Common incidents and resolutions
  - [ ] Monitoring queries (Langfuse, database, Redis)
  - [ ] Performance tuning tips
  - [ ] Backup and recovery
  - [ ] Scaling considerations

**Deliverable**: Complete documentation set

---

#### Day 28 (Nov 28) - Demo Preparation & Launch
**Goal**: Successful Phase 1 demo

- [ ] **Create Demo Script** (30 minutes total)
  1. **Admin Login** (1 min)
     - [ ] Show login page
     - [ ] Enter credentials
     - [ ] Redirect to chat

  2. **Chat Page Overview** (1 min)
     - [ ] Point out category sidebar
     - [ ] Point out search bar
     - [ ] Explain streaming interface

  3. **Product Recommendation Demo** (5 min)
     - [ ] Query: "Best noise-canceling headphones under $300"
     - [ ] Show: Real-time status updates
     - [ ] Show: Product carousel with ≥3 items
     - [ ] Show: Affiliate links (click "Buy Now")
     - [ ] Show: Product images, prices, ratings

  4. **Travel Planning Demo** (5 min)
     - [ ] Query: "Plan a 5-day trip to Paris in April for 2 people"
     - [ ] Show: Follow-up questions for missing slots
     - [ ] Show: Hotel cards (≥5 hotels)
     - [ ] Show: Flight cards (≥3 flights)
     - [ ] Show: Day-by-day itinerary
     - [ ] Click: Hotel deeplink

  5. **Comparison Demo** (3 min)
     - [ ] Query: "Compare MacBook Pro vs Dell XPS"
     - [ ] Show: Product comparison (if implemented)

  6. **Multi-Turn Context Demo** (2 min)
     - [ ] Query: "Tell me about Tokyo"
     - [ ] Query: "What's the best time to visit?"
     - [ ] Query: "Show me hotels there"
     - [ ] Show: Context retention

  7. **Backend Observability** (3 min)
     - [ ] Open Langfuse dashboard
     - [ ] Show traces for last query
     - [ ] Show token usage per agent
     - [ ] Show cost breakdown

  8. **Metrics Dashboard** (3 min)
     - [ ] Open Streamlit dashboard
     - [ ] Show request volume
     - [ ] Show latency charts
     - [ ] Show affiliate CTR
     - [ ] Show cache hit rate

  9. **Mobile Demo** (2 min)
     - [ ] Open on mobile browser
     - [ ] Show responsive design
     - [ ] Show collapsible sidebar

  10. **Phase 1 Complete** (2 min)
      - [ ] Highlight achievements
      - [ ] Show metrics: 19 tools, 5 agents, 419 tests
      - [ ] Revenue-ready MVP!

_This document focuses on REMAINING tasks only. For completed work, see PHASE_1_PROGRESS_TRACKER.md_
