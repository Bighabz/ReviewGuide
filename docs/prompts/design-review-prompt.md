# Design Review Prompt — Paste into Gemini/ChatGPT/Claude

Copy everything below the line and paste it into your AI of choice.

---

You are a senior product designer and frontend architect reviewing a design concept for ReviewGuide.ai — an AI-powered product research and price comparison platform. The site is live at https://www.reviewguide.ai

## The Figma Concept (HTML mockup)

Below is the full HTML of a Figma-exported design concept. It shows a 3-screen user flow: **Discover (mobile) → Chat (mobile) → Results (desktop)**. Open this in a browser or read the code to understand the design:

**Key design decisions in the concept:**
- **Light mode first** — warm cream background (#FAFAF7), white cards
- **3-screen architecture**: Homepage (discover) → Chat (conversation) → Results (product grid + sources panel)
- **Mobile bottom nav** with a floating FAB "Ask" button (circular, blue, elevated with shadow)
- **Category chips** (For You, Tech, Travel, Kitchen...) with active state (dark fill)
- **Trending cards** with gradient emoji backgrounds (blue for headphones, yellow for travel, purple for laptops)
- **Chat screen** has: back button, topic title header, source count, typing dots, suggestion chips
- **Results screen (desktop)** is a 3-column layout:
  - Left: conversation sidebar with chat history list
  - Center: editorial summary + 3-column product card grid (rank badge, score bar, price, CTA)
  - Right: sources panel (RTINGS, Wirecutter, etc. with colored dots) + quick action buttons
- **Product cards** have: gradient image area, rank number badge, "Top Pick"/"Best Value"/"Premium" badges, score bar (e.g., 9.4), price, "Check Price" button
- **Typography**: DM Sans body + Instrument Serif italic for headlines
- **Colors**: #1B4DFF primary blue, #E85D3A terracotta accent, #E8E6E1 borders

## What's Currently Built (v3)

The current live site has these recent changes:
- **Dark mode default** (#0C0E14 blue-black background) — opposite of the Figma's light-first approach
- **Chat-centric UX** — no separate results page, products render inline in chat bubbles
- **Sidebar on homepage** instead of category chips
- **No floating FAB button** in mobile nav
- **No product grid** — products shown as inline cards or carousels within messages
- **No 3-column results layout** — desktop shows chat with sidebar
- **Gradient buy buttons** on product cards (primary→accent gradient)
- **Themed accent picker** (Ocean, Sunset, Neon, Forest, Berry)
- **Streaming improvements** (pulsing dots, stop button, streaming cursor)
- **Bug fixes** (markdown leaking, bubble width, truncated names, history panel)

## What I Need From You

Please review the Figma concept against what's currently built and give me:

### 1. Design Direction Verdict
Should we pursue the Figma's light-mode-first, 3-screen architecture? Or keep the current dark-mode-first, chat-centric approach? Consider:
- Which feels more trustworthy for a product recommendation site?
- Which is more unique/differentiating vs competitors (Amazon, Wirecutter, Perplexity)?
- Which is more practical to build given it's a chat-based AI product?

### 2. Top 5 Elements to Adopt from the Figma
What are the highest-impact design elements from the Figma concept that we should implement, regardless of the overall direction? Rank them.

### 3. What to Keep from v3
What from the current implementation (v3) should we keep even if we adopt the Figma direction?

### 4. What to Skip or Modify
Any elements in the Figma concept that feel wrong, impractical, or would hurt the UX? Be specific.

### 5. Actionable Implementation Priority
Give me an ordered list of changes to make, from highest to lowest impact, that I can hand to a developer. Be specific about components and layouts.

### 6. Dark Mode vs Light Mode
The Figma is light-mode-first. We just shipped dark-mode-first (#0C0E14). Which should be the default? Can we support both well? Does the product category (shopping/reviews) favor one over the other?

Be opinionated. I want strong design opinions, not "it depends." Think like a design lead at Airbnb or Stripe reviewing this before launch.
