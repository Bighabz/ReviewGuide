# ReviewGuide.ai - Application Architecture Diagram

## High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         Next.js Frontend (React + TypeScript)            │  │
│  │  ┌──────────────┐  ┌─────────────────────────────────┐  │  │
│  │  │ Login Page   │  │      Chat Interface             │  │  │
│  │  │ /            │  │  • Category Sidebar             │  │  │
│  │  └──────────────┘  │  • Message List                 │  │  │
│  │                    │  • Streaming Chat Input          │  │  │
│  │                    └─────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ HTTPS/WebSocket (SSE)
                            │ POST /v1/chat/stream
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Python)                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  API Layer                                               │  │
│  │  • POST /v1/auth/login      (JWT Authentication)        │  │
│  │  • POST /v1/chat/stream     (SSE Streaming)             │  │
│  │  • GET  /health              (Health Check)              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                    │
│                            ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         LangGraph Workflow Orchestrator                  │  │
│  │         (StateGraph with GraphState)                     │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  PostgreSQL   │  │     Redis     │  │  External     │
│   Database    │  │     Cache     │  │    APIs       │
│               │  │               │  │               │
│ • Users       │  │ • Sessions    │  │ • OpenAI      │
│ • Sessions    │  │ • Search      │  │   - GPT-4o    │
│ • Conversations│ │   Cache       │  │   - Moderation│
│ • Affiliate   │  │ • State       │  │   - Web Search│
│ • Products    │  │   Storage     │  │ • Perplexity  │
│ • Travel      │  │               │  │ • eBay API    │
│ • Events      │  │               │  │ • Hotels API  │
│               │  │               │  │ • Flights API │
└───────────────┘  └───────────────┘  └───────────────┘
```

## Request Flow Diagram (GENERIC STREAMING ARCHITECTURE 🚀)

```
USER TYPES MESSAGE
        │
        ▼
┌───────────────────────┐
│  Frontend: ChatInput  │
│  • Validates input    │
│  • Creates message UI │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│  Frontend: streamChat │
│  • POST /v1/chat/     │
│    stream             │
│  • Sets up SSE        │
│    connection         │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│  Backend: chat_stream │
│  • Validates request  │
│  • Creates session_id │
│  • Starts SSE stream  │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│  Backend: Creates     │
│  GraphState           │
│  • user_message       │
│  • session_id         │
│  • conversation_history│
│  • stream_chunk_data  │ 🚀 NEW
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│  LangGraph Workflow   │
│  Executes Agents      │
│  (see workflow below) │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│  Result State         │
│  • assistant_text     │
│  • ui_blocks          │
│  • citations          │
│  • status             │
│  • halt               │ 🚀 NEW
│  • stream_chunk_data  │ 🚀 NEW
└───────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  GENERIC SSE STREAMING 🚀           │
│  • Check stream_chunk_data:         │
│    - if exists: stream immediately  │
│    - Extract type & data            │
│    - Check create_new_message flag  │
│  • Check halt status:               │
│    - if halt=true: send followups   │
│    - return (wait for user)         │
│  • Token-by-token response          │
│  • NO hardcoded type checks         │
│  • Agents declare streaming behavior│
└─────────────────────────────────────┘
        │
        ▼
┌───────────────────────┐
│  Frontend: Receives   │
│  tokens via SSE       │
│  • Handles itinerary  │
│  • Handles halt state │
│  • Updates UI         │
│  • Shows streaming    │
└───────────────────────┘
        │
        ▼
    USER SEES
    RESPONSE
```

## LangGraph Workflow - Agent Flow by Intent

**Legend:**
- ✅ IMPL = Implemented in code (backend/app/services/langgraph/workflow.py)
- Function name = Python async function name
- Node name = LangGraph node identifier (used in workflow.add_node() - prefixed with "agent_")

### Common Entry Point (All Intents)

```
┌─────────────────────────────────────┐
│   USER MESSAGE ARRIVES              │
│   GraphState Created                │
│   QueryTracer Initialized           │
└─────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│    1. SAFETY AGENT                  │
│    Function: safety_node()          │
│    Node: "agent_safety" ✅ IMPL     │
│    Class: SafetyAgent               │
│    • OpenAI Moderation API          │
│    • PII Detection & Redaction      │
│    • Jailbreak Detection            │
│    • Check for halted state (Redis) │
│    • Sets: policy_status            │
│       sanitized_text                │
│       redaction_map                 │
└─────────────────────────────────────┘
                 │
  ┌──────────────┼──────────────┐
  │              │              │
[BLOCKED]  [RESUME HALTED] [ALLOWED]
  │              │              │
  ▼              ▼              ▼
 END   ┌──────────────┐  ┌─────────────────────────────────────┐
       │ CLARIFIER/   │  │    2. INTENT & SLOT AGENT          │
       │ TRAVEL_      │  │    Function: intent_node()          │
       │ CLARIFIER    │  │    Node: "agent_intent" ✅ IMPL     │
       │ (RESUME)     │  │    Class: IntentAgent               │
       └──────────────┘  │    • TWO-STEP OPTIMIZED PROCESS:    │
                         │      Step 1: Quick intent classify  │
                         │              (~1s, lightweight)     │
                         │      Step 2: Slot extraction        │
                         │              (~1-2s, focused)       │
                         │    • Classify Intent:               │
                         │      - intro (greetings, help)      │
                         │      - product                      │
                         │      - service                      │
                         │      - travel                       │
                         │      - general                      │
                         │    • Extract Slots (intent-specific)│
                         │    • Check Missing Slots            │
                         │    • Generate Follow-up Questions   │
                         │    • General routing decision       │
                         │    • Sets: intent, slots,           │
                         │       missing_slots, followups      │
                         └─────────────────────────────────────┘
                                     │
          ┌──────────────────────────┼──────────────────────────┐
          │                          │                          │
     [INTRO]                     [TRAVEL]              [PRODUCT/SERVICE]
          │                          │                          │
          ▼                          │                          │
   ┌──────────────┐                 │                          │
   │ INTRO AGENT  │                 │                          │
   │ → END        │                 │                          │
   └──────────────┘                 │                          │
                                    │                          │
                    See diagrams below for full flows          │
                                    ▼                          ▼
```

### TRAVEL Intent Flow

```
┌─────────────────────────────────────┐
│ 3a. TRAVEL CLARIFIER AGENT 🚀      │
│    Function: travel_clarifier_node()│
│    Node: "agent_travel_clarifier"   │
│    ✅ IMPL                          │
│    Class: TravelClarifierAgent      │
│    • Check showed_itinerary flag    │
│    • Validate travel slots:         │
│      - destination                  │
│      - check_in, check_out          │
│      - travelers, budget            │
│    • ROUTING LOGIC:                 │
│      IF slots incomplete AND        │
│         !showed_itinerary:          │
│        → travel_itinerary           │
│      IF slots incomplete AND        │
│         showed_itinerary:           │
│        → HALT (ask followups)       │
│      IF slots complete:             │
│        → travel_planner             │
│    • HaltStateManager integration   │
└─────────────────────────────────────┘
                 │
  ┌──────────────┼──────────────┐
  │              │              │
[NO ITINERARY] [HALTED]  [ALL SLOTS OK]
  │              │              │
  ▼              ▼              ▼
┌─────────────────────────────────────┐
│ 3b. TRAVEL ITINERARY AGENT 🚀      │
│    Function: travel_itinerary_node()│
│    Node: "agent_travel_itinerary"   │
│    ✅ IMPL                          │
│    Class: TravelItineraryAgent      │
│    • Generate day-by-day itinerary  │
│      using LLM                      │
│    • Include activities, meals,     │
│      landmarks                      │
│    • Create stream_chunk_data:      │
│      {                              │
│        "type": "itinerary",         │
│        "data": [...],               │
│        "create_new_message": true   │
│      }                              │
│    • Set showed_itinerary=True      │
│      in HaltStateManager            │
│    • ALWAYS route back to           │
│      travel_clarifier to validate   │
└─────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│ 3a. TRAVEL CLARIFIER (2nd call)     │
│    • Showed_itinerary = true        │
│    • Slots still incomplete         │
│    → HALT with followups            │
│    (Wait for user response)         │
└─────────────────────────────────────┘
                 │
      [USER PROVIDES MISSING INFO]
                 │
                 ▼
┌─────────────────────────────────────┐
│ 3a. TRAVEL CLARIFIER (3rd call)     │
│    • All slots now complete         │
│    • Route to travel_planner        │
└─────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│ 3c. TRAVEL PLANNER AGENT 🚀        │
│    Function: travel_planner_node()  │
│    Node: "agent_travel_planner"     │
│    ✅ IMPL                          │
│    Class: TravelPlannerAgent        │
│    • Search hotels (API)            │
│    • Search flights (API)           │
│    • REUSE existing itinerary       │
│      from state (NOT regenerate)    │
│    • Sets: hotels, flights          │
│    • Route to composer              │
└─────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│  8. COMPOSER AGENT                  │
│  Function: composer_node()          │
│  Node: "agent_composer" ✅ IMPL     │
│  Class: ComposerAgent               │
│  • Generate final text + UI blocks  │
│  • Intent: travel                   │
│    - hotels + flights cards         │
│    - itinerary NOT shown again      │
│  • Sets: assistant_text,            │
│     ui_blocks, citations,           │
│     status="completed"              │
└─────────────────────────────────────┘
                 │
                 ▼
           [END - Stream to Frontend]
```

### PRODUCT/SERVICE Intent Flow

```
┌─────────────────────────────────────┐
│ 3. CLARIFIER AGENT                  │
│    Function: clarifier_node()       │
│    Node: "agent_clarifier" ✅ IMPL  │
│    Class: ClarifierAgent            │
│    • Check if slots missing         │
│    • HALT if missing (Redis state)  │
│    • RESUME when user answers       │
│    • Updates slots                  │
│    • Sets: status ="halted" or      │
│       status= "running"             │
└─────────────────────────────────────┘
                 │
  ┌──────────────┴──────────────┐
  │                             │
[MISSING SLOTS]          [SLOTS COMPLETE]
  │                             │
  ▼                             ▼
HALT                 ┌─────────────────────────────────────┐
(followups)          │    4. SEARCH AGENT                  │
                     │    Function: search_node()          │
                     │    Node: "agent_search" ✅ IMPL     │
                     │    Class: SearchAgent               │
                     │    • Generate Search Query          │
                     │    • Redis Cache Check              │
                     │    • SearchProvider (configurable)  │
                     │      - OpenAI (current default)     │
                     │      - Perplexity                   │
                     │      - Tavily, Bing, etc.           │
                     │    • Product Name Extraction (LLM)  │
                     │    • Result Deduplication           │
                     │    • Authority Ranking              │
                     │    • Sets: search_results,          │
                     │       search_query, product_names   │
                     └─────────────────────────────────────┘
                                     │
                      ┌──────────────┼──────────────┐
                      │              │              │
                  [PRODUCT]      [SERVICE]      [GENERAL]
                      │              │              │
                      ▼              ▼              ▼
           ┌──────────────────┐      │              │
           │ 5. PARALLEL      │      │              │
           │    PRODUCT       │      │              │
           │    NODE 🚀       │      │              │
           │  Function:       │      │              │
           │  parallel_       │      │              │
           │  product_node()  │      │              │
           │  Node:           │      │              │
           │  "agent_parallel │      │              │
           │   _product"      │      │              │
           │  ✅ IMPL         │      │              │
           │  • Runs Evidence │      │              │
           │    & Affiliate   │      │              │
           │    in parallel   │      │              │
           │  • For each      │      │              │
           │    product name  │      │              │
           │  • Sets:         │      │              │
           │    review_       │      │              │
           │    aspects,      │      │              │
           │    affiliate_    │      │              │
           │    links         │      │              │
           └──────────────────┘      │              │
                      │              │              │
                      ▼              │              │
           ┌──────────────────┐      │              │
           │ 6. RANKING       │      │              │
           │    AGENT         │      │              │
           │  Function:       │      │              │
           │  ranking_node()  │      │              │
           │  Node:           │      │              │
           │  "agent_ranking" │      │              │
           │  ✅ IMPL         │      │              │
           │  Class:          │      │              │
           │  RankingAgent    │      │              │
           │  • Rank/         │      │              │
           │    diversify     │      │              │
           │    items         │      │              │
           │  • Sets:         │      │              │
           │    ranked_items  │      │              │
           └──────────────────┘      │              │
                      │              │              │
                      ▼              │              │
           ┌──────────────────┐      │              │
           │ 7. NORMALIZATION │      │              │
           │    AGENT         │      │              │
           │  Function:       │      │              │
           │  normalization_  │      │              │
           │    node()        │      │              │
           │  Node:           │      │              │
           │  "agent_         │      │              │
           │   normalization" │      │              │
           │  ✅ IMPL         │      │              │
           │  Class:          │      │              │
           │  Normalization   │      │              │
           │    Agent         │      │              │
           │  • Merge         │      │              │
           │    evidence      │      │              │
           │    + affiliate   │      │              │
           │    + ranking     │      │              │
           │  • Match by      │      │              │
           │    product name  │      │              │
           │  • Sets:         │      │              │
           │    normalized_   │      │              │
           │    products      │      │              │
           └──────────────────┘      │              │
                      │              │              │
                      └──────────────┴──────────────┘
                                     │
                                     ▼
                     ┌─────────────────────────────────────┐
                     │  8. COMPOSER AGENT                  │
                     │  Function: composer_node()          │
                     │  Node: "agent_composer" ✅ IMPL     │
                     │  Class: ComposerAgent               │
                     │  • Generate final text + UI blocks  │
                     │  • Intent: product/service          │
                     │    - carousel + reviews             │
                     │    - pros_cons                      │
                     │  • Sets: assistant_text,            │
                     │     ui_blocks, citations,           │
                     │     status="completed"              │
                     └─────────────────────────────────────┘
                                     │
                                     ▼
                               [END - Stream to Frontend]
```

### Final Output (All Intents)

```
┌─────────────────────────────────────┐
│   FINAL GRAPHSTATE                   │
│   • assistant_text                   │
│   • ui_blocks                        │
│   • citations                        │
│   • status: "completed"              │
│   • QueryTracer metrics:             │
│     - total_cost_usd                 │
│     - total_tokens                   │
│     - cache_hits                     │
└─────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│   SSE STREAM TO FRONTEND             │
│   Token-by-token streaming           │
│   Langfuse traces flushed            │
└─────────────────────────────────────┘
```

## GraphState Evolution Through Workflow

### Product Intent Example
```
INITIAL STATE
├── user_message: "Best laptop for programming"
├── session_id: "abc-123"
├── conversation_history: []
└── status: "running"
     │
     ▼ (After Safety Agent)
├── policy_status: "allow"
├── sanitized_text: "Best laptop for programming"
├── current_agent: "safety"
└── next_agent: "intent"
     │
     ▼ (After Intent Agent)
├── intent: "product"
├── slots: {"product_type": "laptop", "use_case": "programming"}
├── missing_slots: ["budget"]
├── current_agent: "intent"
└── next_agent: "clarifier"
     │
     ▼ (After Clarifier - HALT example)
├── status: "halted"
├── halt: true  🚀 NEW
├── halt_reason: "missing_budget"
├── followups: ["What's your budget range?"]
└── (Wait for user response, then RESUME)
     │
     ▼ (After Search Orchestrator)
├── search_results: [{...}, {...}, {...}]
├── search_query: "best programming laptop 2024"
├── product_names: ["MacBook Pro", "ThinkPad X1"] 🚀 NEW
└── next_agent: "parallel_product"
     │
     ▼ (After Parallel Product Node - Evidence + Affiliate in parallel)
├── review_aspects: [{"product": "MacBook Pro", "pros": [...], "cons": [...]}]
├── affiliate_links: [{"product": "MacBook Pro", "url": "...", "merchant": "eBay"}]
└── next_agent: "ranking"
     │
     ▼ (After Ranking)
├── ranked_items: [{rank: 1, score: 9.5}, ...]
└── next_agent: "normalization"
     │
     ▼ (After Normalization - Merges evidence + affiliate + ranking)
├── normalized_products: [{"name": "MacBook Pro", "evidence": {...}, "affiliate": {...}, "rank": 1}]
└── next_agent: "composer"
     │
     ▼ (After Composer)
├── assistant_text: "Here are the best laptops..."
├── ui_blocks: [{"type": "carousel", "items": [...]}, {"type": "product_review", ...}]
├── citations: ["[1]", "[2]", "[3]"]
└── status: "completed"
```

### Travel Intent Example 🚀 NEW
```
INITIAL STATE
├── user_message: "I want to travel to Tokyo"
├── session_id: "xyz-456"
└── status: "running"
     │
     ▼ (After Safety & Intent Agents)
├── intent: "travel"
├── slots: {"destination": "Tokyo"}
├── missing_slots: ["check_in", "check_out", "travelers"]
└── next_agent: "travel_clarifier"
     │
     ▼ (After Travel Clarifier - First Call)
├── showed_itinerary: false  🚀 NEW
└── next_agent: "travel_itinerary"  (Missing slots + no itinerary shown)
     │
     ▼ (After Travel Itinerary Agent)
├── itinerary: [{day: 1, activities: [...]}, {day: 2, ...}]
├── stream_chunk_data: {  🚀 NEW - Streamed immediately to browser
│     "type": "itinerary",
│     "data": [...],
│     "create_new_message": true
│   }
├── showed_itinerary: true  🚀 NEW (saved to Redis halt state)
└── next_agent: "travel_clarifier"  (Route back to check slots)
     │
     ▼ (After Travel Clarifier - Second Call)
├── Still missing: ["check_in", "check_out", "travelers"]
├── status: "halted"
├── halt: true  🚀 NEW
├── followups: ["When would you like to check in?", ...]
└── (Wait for user response)
     │
     ▼ (User: "Check in Dec 1, check out Dec 5, 2 travelers")
     │
     ▼ (After Travel Clarifier - Resume)
├── slots: {"destination": "Tokyo", "check_in": "2024-12-01", "check_out": "2024-12-05", "travelers": 2}
├── halt: false
├── showed_itinerary: true  🚀 NEW (loaded from Redis halt state)
└── next_agent: "travel_planner"  (All slots complete)
     │
     ▼ (After Travel Planner)
├── hotels: [{name: "...", price: ...}, ...]
├── flights: [{airline: "...", price: ...}, ...]
├── itinerary: [...]  (Reused from state, NOT regenerated)
└── next_agent: "composer"
     │
     ▼ (After Composer)
├── assistant_text: "Here's your complete travel plan..."
├── ui_blocks: [{"type": "hotel_cards", ...}, {"type": "flight_cards", ...}]
│   (Note: itinerary NOT in ui_blocks - already shown earlier)
└── status: "completed"
```

## Agent Implementation Status

### Currently Implemented (✅): 13 Agents + Base Class + State Management

1. **BaseAgent** → Base class for all agents
   - Location: `backend/app/agents/base_agent.py`
   - Features: Common agent interface, model service integration, error handling

2. **SafetyAgent** → Node: `"agent_safety"`
   - Location: `backend/app/agents/safety_agent.py`
   - Wrapper: `workflow.safety_node()` in `workflow.py:42`
   - Features: OpenAI Moderation API, PII detection, jailbreak detection, halt state checking

3. **IntentAgent** → Node: `"agent_intent"` 🚀 OPTIMIZED
   - Location: `backend/app/agents/intent_agent.py`
   - Wrapper: `workflow.intent_node()` in `workflow.py:115`
   - Features:
     - Two-step optimized process (15x faster: ~30s → ~2-3s)
     - Quick intent classification (~1s, lightweight)
     - Intent-specific slot extraction (~1-2s, focused)
     - Dynamic routing for "general" intent (search vs. no-search)
     - Supports: intro, product, service, travel, general
     - Follow-up question generation

4. **IntroAgent** → Node: `"agent_intro"` 🆕 NEW
   - Location: `backend/app/agents/intro_agent.py`
   - Wrapper: `workflow.intro_node()` in `workflow.py:190`
   - Features:
     - Handles greetings ("hi", "hello", "hey")
     - Explains chatbot capabilities
     - Friendly 2-4 sentence responses
     - Routes directly to END (no further processing)

5. **ClarifierAgent** → Node: `"agent_clarifier"`
   - Location: `backend/app/agents/clarifier_agent.py`
   - Wrapper: `workflow.clarifier_node()` in `workflow.py:217`
   - Features: HALT/RESUME mechanism, HaltStateManager integration, slot updates

6. **TravelClarifierAgent** → Node: `"agent_travel_clarifier"` 🚀 NEW
   - Location: `backend/app/agents/travel_clarifier_agent.py`
   - Wrapper: `workflow.travel_clarifier_node()`
   - Features:
     - Travel-specific slot validation (destination, dates, travelers, budget)
     - Checks showed_itinerary flag from HaltStateManager
     - Routes to travel_itinerary if slots incomplete AND no itinerary shown
     - HALT if slots incomplete AND itinerary already shown
     - Routes to travel_planner if all slots complete
     - HaltStateManager integration for state persistence

7. **TravelItineraryAgent** → Node: `"agent_travel_itinerary"` 🚀 NEW
   - Location: `backend/app/agents/travel_itinerary_agent.py`
   - Wrapper: `workflow.travel_itinerary_node()`
   - Features:
     - Generates day-by-day travel itinerary using LLM
     - Creates stream_chunk_data with create_new_message flag
     - Sets showed_itinerary=True in HaltStateManager
     - Routes back to travel_clarifier for validation
     - Immediate streaming to browser before HALT

8. **TravelPlannerAgent** → Node: `"agent_travel_planner"` 🚀 UPDATED
   - Location: `backend/app/agents/travel_planner_agent.py`
   - Wrapper: `workflow.travel_planner_node()`
   - Features:
     - Hotel API search integration
     - Flight API search integration
     - Reuses existing itinerary from state (NOT regenerated)
     - Routes to composer with hotels + flights

9. **SearchAgent** → Node: `"agent_search"`
   - Location: `backend/app/agents/search_agent.py`
   - Wrapper: `workflow.search_node()` in `workflow.py:265`
   - Features: Configurable search providers (OpenAI current default, Perplexity available), Product name extraction using LLM, Redis caching, result deduplication, authority ranking

10. **EvidenceAgent** → Node: `"agent_evidence"` 🚀 PARALLEL
    - Location: `backend/app/agents/evidence_agent.py`
    - Wrapper: `workflow.parallel_product_node()` in `workflow.py:278-323`
    - Features: Parallel product evidence extraction, pros/cons analysis per product, citation tracking, features extraction, rating generation

11. **AffiliateAgent** → Node: `"agent_affiliate"` 🚀 PARALLEL
    - Location: `backend/app/agents/affiliate_agent.py`
    - Wrapper: `workflow.parallel_product_node()` in `workflow.py:278-323`
    - Features: Parallel eBay API searches by product name, top 3 affiliate links per product, link health validation

12. **NormalizationAgent** → Node: `"agent_normalization"` (REFACTORED)
    - Location: `backend/app/agents/normalization_agent.py`
    - Wrapper: `workflow.normalization_node()` in `workflow.py:347`
    - Features: Merges evidence + affiliate + ranking data, matches products by name, creates normalized_products list

13. **RankingAgent** → Node: `"agent_ranking"`
    - Location: `backend/app/agents/ranking_agent.py`
    - Wrapper: `workflow.ranking_node()` in `workflow.py:418`
    - Features: Product ranking, diversification, relevance scoring

14. **ComposerAgent** → Node: `"agent_composer"` (ENHANCED)
    - Location: `backend/app/agents/composer_agent.py`
    - Wrapper: `workflow.composer_node()` in `workflow.py:453`
    - Features: Intent-based routing, GPT-4o responses, UI block generation (carousel, product_review, pros_cons, hotel_cards, flight_cards), handles products without affiliate links

15. **route_next_agent()** → Routing function
    - Location: `backend/app/services/langgraph/workflow.py:489`
    - Determines next agent based on state.next_agent field

### State Management Services 🚀 NEW

16. **HaltStateManager** → Centralized halt state management
    - Location: `backend/app/services/halt_state_manager.py`
    - Features:
      - Two-tier caching architecture (Process cache + Redis)
      - Dynamic field preservation (no hardcoded fields)
      - Methods: get_halt_state(), update_halt_state(), update_field(), delete_halt_state(), check_if_resume()
      - TTL: 1 hour (3600 seconds)
      - Intent change detection (clears halt state if intent changes)

17. **SlotAccessor** → Slot access utilities
    - Location: `backend/app/services/slot_accessor.py`
    - Features: Centralized slot reading/writing utilities

### Observability & Tracing (✅):
- **OpenTelemetry Integration** → `backend/app/core/observability.py`
  - HTTP request tracing
  - Agent execution spans
  - Langfuse OTLP export (optional)

- **QueryTracer** → `backend/app/core/custom_tracing.py`
  - End-to-end query tracing
  - Cost and token tracking
  - Cache hit/miss tracking
  - Agent-level metrics

- **ModelService** → `backend/app/services/model_service.py`
  - LiteLLM integration
  - Token counting and cost tracking
  - Langfuse generation tracking

### Recent Optimizations:
- **Generic Streaming Architecture** 🚀 (Latest): Agents declare streaming via stream_chunk_data, API layer just forwards without type checks
- **Travel Multi-Stage Flow** 🚀 (Latest): Show itinerary FIRST, then ask for missing slots, then book hotels/flights
- **HaltStateManager with Dynamic Fields** 🚀 (Latest): Two-tier caching + automatic field preservation without hardcoding
- **Node Wrapper Pass-Through** 🚀 (Latest): Workflow nodes explicitly pass through stream_chunk_data field
- **Product Search Flow** (Earlier): Parallel processing of Evidence + Affiliate agents → ~70% speed improvement for product searches
- **Search Provider** (Earlier): Added OpenAI web search provider as default, configurable via YAML
- **Product Name Extraction** (Earlier): LLM-based extraction from search results for more accurate affiliate matching
- **Normalization Agent** (Earlier): Refactored from entity extraction to data merging role
- **Intent Agent** (Nov 7, 2025): Split monolithic LLM call into 2 sequential lightweight calls → 15x performance improvement
- **Intro Agent** (Nov 7, 2025): Added dedicated agent for greetings and capability explanations

## Key Architectural Improvements (Latest) 🚀

### 1. Generic Streaming Architecture
**Problem**: System had hardcoded logic for streaming itinerary data in chat.py, violating separation of concerns.

**Solution**: Implemented completely generic streaming where agents declare what to stream:
```python
# In any agent (e.g., travel_itinerary_agent.py):
stream_chunk_data = {
    "type": "itinerary",
    "data": itinerary,
    "create_new_message": True  # Optional flag
}
return {
    "itinerary": itinerary,
    "stream_chunk_data": stream_chunk_data,
    "next_agent": "travel_clarifier"
}
```

**Benefits**:
- **No hardcoded logic in API layer**: chat.py simply forwards whatever stream_chunk_data exists
- **Agent autonomy**: Each agent controls its own streaming behavior declaratively
- **Extensibility**: New data types can be streamed without touching chat.py
- **Declarative flags**: Agents specify create_new_message flag to control message boundaries

**Files Changed**:
- [backend/app/api/v1/chat.py](backend/app/api/v1/chat.py) - Generic streaming logic (lines 346-371)
- [backend/app/agents/travel_itinerary_agent.py](backend/app/agents/travel_itinerary_agent.py) - Example usage (lines 80-91)
- [backend/app/services/langgraph/workflow.py](backend/app/services/langgraph/workflow.py) - Pass through stream_chunk_data (lines 577-579)
- [backend/app/schemas/graph_state.py](backend/app/schemas/graph_state.py) - Added stream_chunk_data field (line 69)

### 2. Travel Multi-Stage Flow
**Problem**: Travel planning was generating itinerary at the END (after booking), but UX required showing itinerary FIRST.

**Solution**: Implemented multi-stage travel flow:
1. **Stage 1 - Slot Collection**: Travel Clarifier → Itinerary Agent (generate & stream) → Travel Clarifier (HALT with follow-ups)
2. **Stage 2 - Booking**: Resume → Travel Clarifier (validate slots) → Travel Planner (book hotels/flights with existing itinerary)

**Key Features**:
- Itinerary shown BEFORE asking for missing slots (better UX)
- showed_itinerary flag prevents duplicate itinerary display
- Travel Planner reuses existing itinerary instead of regenerating
- All slots validated before booking APIs are called

**Files Changed**:
- [backend/app/agents/travel_clarifier_agent.py](backend/app/agents/travel_clarifier_agent.py) - Slot validation & routing logic
- [backend/app/agents/travel_itinerary_agent.py](backend/app/agents/travel_itinerary_agent.py) - Itinerary generation
- [backend/app/agents/travel_planner_agent.py](backend/app/agents/travel_planner_agent.py) - Reuse existing itinerary (lines 118-126)

### 3. HaltStateManager with Dynamic Fields
**Problem**: HaltStateManager only saved hardcoded fields (intent, slots, followups), requiring code changes for new fields.

**Solution**: Implemented fully dynamic field preservation:
```python
# In update_halt_state():
# Start with core fields
halt_state_data = {
    "intent": result_state.get("intent"),
    "slots": result_state.get("slots", {}),
    "followups": result_state.get("followups", []),
    "halt_reason": result_state.get("halt_reason"),
}

# Preserve ANY additional fields dynamically
for key, value in result_state.items():
    if key not in halt_state_data and not key.startswith("_"):
        halt_state_data[key] = value  # e.g., showed_itinerary, travel_info
```

**Architecture**:
- **Process-level cache**: Fast access, no Redis calls within same request
- **Redis persistent storage**: Survives across requests, 1-hour TTL
- **Dynamic field preservation**: No hardcoded field names
- **Intent change detection**: Automatically clears halt state if intent changes

**Key Methods**:
- `get_halt_state(session_id)` - Checks cache first, then Redis
- `update_halt_state(session_id, result_state)` - Updates cache AND Redis
- `update_field(session_id, field_name, value)` - Updates single field, creates if doesn't exist
- `delete_halt_state(session_id)` - Clears cache AND Redis
- `check_if_resume(session_id, intent)` - Checks if resuming valid halt state

**Files Changed**:
- [backend/app/services/halt_state_manager.py](backend/app/services/halt_state_manager.py) - Complete implementation with all methods
- [backend/app/agents/travel_clarifier_agent.py](backend/app/agents/travel_clarifier_agent.py) - Usage example
- [backend/app/agents/travel_itinerary_agent.py](backend/app/agents/travel_itinerary_agent.py) - Sets showed_itinerary flag (lines 87-91)

### 4. Node Wrapper Pattern for State Pass-Through
**Problem**: LangGraph node wrappers were dropping important fields like stream_chunk_data.

**Solution**: Node wrappers now explicitly pass through all streaming-related fields:
```python
# In workflow.py - travel_itinerary_node:
async def travel_itinerary_node(state: GraphState) -> Dict[str, Any]:
    result = await travel_itinerary_agent.execute(state)

    update = {
        "itinerary": result.get("itinerary", []),
        "current_agent": "travel_itinerary",
        "next_agent": result.get("next_agent", "travel_clarifier"),
    }

    # Pass through stream_chunk_data for immediate streaming
    if result.get("stream_chunk_data"):
        update["stream_chunk_data"] = result["stream_chunk_data"]

    return update
```

**Benefits**:
- Ensures all streaming data reaches the API layer
- Agents' declarative streaming instructions are preserved
- Supports any future streaming fields without code changes

**Files Changed**:
- [backend/app/services/langgraph/workflow.py](backend/app/services/langgraph/workflow.py) - All node wrappers updated

## Data Flow Summary

**Request Path:**
User → Frontend → FastAPI → LangGraph → Agents → External APIs/DBs → LangGraph → FastAPI → SSE Stream → Frontend → User

**State Path:**
GraphState created → Passed through each agent → Each agent reads/writes → Final state returned → Extracted for response

**Streaming Path:**
LangGraph completes → Response text extracted → Tokenized → SSE stream → Frontend receives tokens → UI updates in real-time

**Code Locations:**

**Core Workflow & State:**
- Workflow definition: `backend/app/services/langgraph/workflow.py` - LangGraph StateGraph with node wrappers
- GraphState schema: `backend/app/schemas/graph_state.py` - Shared state with stream_chunk_data field
- Chat endpoint: `backend/app/api/v1/chat.py` - Generic SSE streaming endpoint

**Agents:**
- Base: `backend/app/agents/base_agent.py`
- Safety: `backend/app/agents/safety_agent.py`
- Intent: `backend/app/agents/intent_agent.py`
- Intro: `backend/app/agents/intro_agent.py`
- Clarifier: `backend/app/agents/clarifier_agent.py`
- Travel Clarifier: `backend/app/agents/travel_clarifier_agent.py` 🚀 NEW
- Travel Itinerary: `backend/app/agents/travel_itinerary_agent.py` 🚀 NEW
- Travel Planner: `backend/app/agents/travel_planner_agent.py` 🚀 UPDATED
- Search: `backend/app/agents/search_agent.py`
- Evidence: `backend/app/agents/evidence_agent.py`
- Affiliate: `backend/app/agents/affiliate_agent.py`
- Normalization: `backend/app/agents/normalization_agent.py`
- Ranking: `backend/app/agents/ranking_agent.py`
- Composer: `backend/app/agents/composer_agent.py`

**State Management:** 🚀 NEW
- HaltStateManager: `backend/app/services/halt_state_manager.py` - Two-tier caching with dynamic fields
- SlotAccessor: `backend/app/services/slot_accessor.py` - Centralized slot utilities

**Services:**
- Model service: `backend/app/services/model_service.py` - LiteLLM integration
- Search manager: `backend/app/services/search/manager.py`
- Search providers: `backend/app/services/search/providers/*.py` (openai_provider, perplexity_provider)
- Search config: `backend/config/search.yaml`

**Observability:**
- OpenTelemetry: `backend/app/core/observability.py`
- QueryTracer: `backend/app/core/custom_tracing.py`

**Frontend:**
- Chat Container: `frontend/components/ChatContainer.tsx` - Main chat interface with streaming
- Product Carousel: `frontend/components/ProductCarousel.tsx`
- Product Review: `frontend/components/ProductReview.tsx`
- Chat API: `frontend/lib/chatApi.ts` - SSE client

