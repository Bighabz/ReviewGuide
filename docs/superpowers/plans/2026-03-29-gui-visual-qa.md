# ReviewGuide.ai — Full GUI Visual QA Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Visually verify every page and interactive element on the live site (https://www.reviewguide.ai) using Chrome MCP screenshots at both mobile (390x844) and desktop (1280x800) viewports.

**Architecture:** Each task navigates to a specific page/state, takes screenshots, zooms into key elements, and logs pass/fail for each visual check. No code changes — pure visual QA. Failures are collected into a fix list at the end.

**Tech Stack:** Chrome MCP (screenshot, navigate, resize_window, find, computer actions), live Vercel deploy

**Test Site:** `https://www.reviewguide.ai`

---

## Phase 1: Homepage

### Task 1: Homepage — Mobile (390x844)

**Target:** `https://www.reviewguide.ai` at 390x844

- [ ] **Step 1: Set viewport and navigate**
  - `resize_window(390, 844)`
  - `navigate("https://www.reviewguide.ai")`
  - Wait 3s for hydration

- [ ] **Step 2: Full-page screenshot**
  - `screenshot()` — capture the entire viewport
  - **Verify:** All of these visible without scrolling:
    - Header: "ReviewGuide" serif italic logo + gradient avatar
    - Hero: "What are you *researching* today?" + subtitle
    - Category chips: "For You" (dark active), Tech, Travel, Kitchen, Fitness, Audio
    - Product carousel card with gradient, icon, tag, score, title, price
    - Dot indicators below carousel
    - Search bar with visible border
    - Bottom tab bar (Home active, History, Saved, Settings)

- [ ] **Step 3: Zoom into header**
  - `zoom(0, 0, 500, 55)` — verify logo text is serif italic, avatar is gradient circle

- [ ] **Step 4: Zoom into category chips**
  - `zoom(0, 160, 500, 200)` — verify "For You" has dark fill, others have white bg + border

- [ ] **Step 5: Zoom into carousel card**
  - `zoom(0, 230, 500, 470)` — verify:
    - Gradient hero area with icon in white glass card
    - Tag badge (TOP PICK / EDITOR PICK etc.) top-left
    - Score badge (star + number) top-right
    - Title, subtitle, price below
    - "Research →" CTA link

- [ ] **Step 6: Zoom into search bar**
  - `zoom(0, 480, 500, 540)` — verify visible border (2px), search icon, placeholder text, mic icon

- [ ] **Step 7: Zoom into tab bar**
  - `zoom(0, 640, 500, 700)` — verify 4 tabs: Home (active/blue), History, Saved, Settings

- [ ] **Step 8: Wait for carousel auto-rotate**
  - `wait(5)` — carousel should auto-advance
  - `screenshot()` — verify different slide is now showing (different gradient/title)

- [ ] **Step 9: Log results**
  - Record pass/fail for each element

---

### Task 2: Homepage — Desktop (1280x800)

**Target:** `https://www.reviewguide.ai` at 1280x800

- [ ] **Step 1: Set viewport and navigate**
  - `resize_window(1280, 800)`
  - `navigate("https://www.reviewguide.ai")`
  - Wait 3s

- [ ] **Step 2: Full-page screenshot**
  - **Verify:**
    - UnifiedTopbar: serif "ReviewGuide" logo, nav tabs (Discover active, Saved, Ask, Compare, Profile), search bar, New Chat button, theme toggle, palette icon, gradient avatar
    - CategorySidebar visible on left (Quick Searches + Categories)
    - Hero text centered
    - Category chips row
    - Product carousel (wider card)
    - Search bar below
    - No bottom tab bar (desktop)

- [ ] **Step 3: Zoom into topbar**
  - `zoom(0, 0, 1280, 60)` — verify serif logo, nav items, search input, action buttons

- [ ] **Step 4: Zoom into sidebar**
  - `zoom(0, 60, 200, 600)` — verify Quick Searches list + Categories list

- [ ] **Step 5: Zoom into carousel (desktop)**
  - Verify wider card renders correctly, prev/next arrows visible on desktop

- [ ] **Step 6: Log results**

---

## Phase 2: Chat Page

### Task 3: Chat Page — Mobile (390x844)

**Target:** `https://www.reviewguide.ai/chat` at 390x844

- [ ] **Step 1: Set viewport and navigate**
  - `resize_window(390, 844)`
  - `navigate("https://www.reviewguide.ai/chat")`
  - Wait 3s

- [ ] **Step 2: Full screenshot**
  - **Verify:**
    - MobileHeader: back arrow, session title, "Researching" subtitle, share button
    - Header bg is white (var(--surface)) not ivory
    - Chat content area with messages
    - Chat input bar ("Ask anything") with mic, attachment, send icons
    - Bottom tab bar (History active)

- [ ] **Step 3: Zoom into chat header**
  - `zoom(0, 0, 500, 55)` — verify white bg, back arrow, truncated title, share icon

- [ ] **Step 4: Zoom into chat input area**
  - `zoom(0, 580, 500, 650)` — verify input bar is visible and not cut off

- [ ] **Step 5: Zoom into tab bar**
  - `zoom(0, 640, 500, 700)` — verify History tab is active (blue)

- [ ] **Step 6: Log results**

---

### Task 4: Chat Page — Desktop Split-Pane (1280x800)

**Target:** `https://www.reviewguide.ai/chat` at 1280x800

- [ ] **Step 1: Set viewport and navigate**
  - `resize_window(1280, 800)`
  - `navigate("https://www.reviewguide.ai/chat")`
  - Wait 3s

- [ ] **Step 2: Full screenshot**
  - **Verify:**
    - UnifiedTopbar with "Ask" tab active
    - Split-pane: left chat (380px) + right results panel
    - Left pane: user message bubble (blue), AI response with "ReviewGuide" label
    - Right pane: "Research Results" serif italic header + Share/Save/Refresh buttons
    - Sources section with colored dots

- [ ] **Step 3: Zoom into left pane**
  - `zoom(0, 60, 380, 650)` — verify chat messages render correctly, input at bottom

- [ ] **Step 4: Zoom into results panel header**
  - `zoom(380, 60, 1280, 120)` — verify serif title, white bg, action buttons

- [ ] **Step 5: Zoom into sources section**
  - `zoom(380, 250, 1280, 550)` — verify source names with colored dots, clickable links

- [ ] **Step 6: Log results**

---

## Phase 3: Interactive Elements

### Task 5: Search Bar Functionality (Mobile)

**Target:** Homepage search bar at 390x844

- [ ] **Step 1: Navigate to homepage, mobile viewport**

- [ ] **Step 2: Find and click the search bar**
  - `find("search bar")` or click on the input area
  - **Verify:** Input gains focus, cursor appears

- [ ] **Step 3: Type a query**
  - `type("best wireless earbuds")` into the search input
  - `screenshot()` — verify typed text appears in the input

- [ ] **Step 4: Submit the form**
  - `key("Enter")` to submit
  - `wait(3)` — should navigate to `/chat?q=best+wireless+earbuds&new=1`
  - `screenshot()` — verify we're on the chat page with the query

- [ ] **Step 5: Log results**

---

### Task 6: Category Chip Navigation (Mobile)

**Target:** Homepage chips at 390x844

- [ ] **Step 1: Navigate to homepage**

- [ ] **Step 2: Click "Tech" chip**
  - Find and click the "Tech" chip
  - `wait(3)` — should navigate to `/chat?q=...&new=1`
  - `screenshot()` — verify chat page loads with tech-related query

- [ ] **Step 3: Navigate back, click "Travel" chip**
  - Navigate back to `/`
  - Click "Travel" chip
  - Verify navigation to chat with travel query

- [ ] **Step 4: Log results**

---

### Task 7: Product Carousel Interaction (Mobile)

**Target:** Homepage carousel at 390x844

- [ ] **Step 1: Navigate to homepage**

- [ ] **Step 2: Screenshot initial slide**
  - Note which product is showing (title, gradient color)

- [ ] **Step 3: Swipe left on carousel**
  - Touch start at (350, 350), touch end at (100, 350) — swipe left
  - `screenshot()` — verify different slide is now showing

- [ ] **Step 4: Click on carousel card**
  - Click on the card body
  - `wait(3)` — verify navigation to `/chat?q=...&new=1`

- [ ] **Step 5: Log results**

---

### Task 8: Tab Bar Navigation (Mobile)

**Target:** Bottom tab bar at 390x844

- [ ] **Step 1: From homepage, verify Home tab is active**
  - `zoom` into tab bar — Home should be blue

- [ ] **Step 2: Tap "History" tab**
  - Click History tab icon
  - `wait(2)` — should navigate to `/chat`
  - `screenshot()` — verify chat page, History tab now active

- [ ] **Step 3: Tap "Saved" tab**
  - Click Saved tab icon
  - `wait(2)` — should navigate to `/saved`
  - `screenshot()` — verify saved page loads

- [ ] **Step 4: Tap "Home" tab**
  - Click Home tab icon
  - `wait(2)` — should navigate to `/`
  - `screenshot()` — verify homepage, Home tab active again

- [ ] **Step 5: Tap "Settings" icon**
  - Click Settings gear icon
  - `screenshot()` — verify settings popover opens (theme toggle + accent colors)

- [ ] **Step 6: Log results**

---

## Phase 4: Theme & Accent

### Task 9: Theme Toggle (Desktop)

**Target:** Desktop topbar theme toggle at 1280x800

- [ ] **Step 1: Navigate to homepage at 1280x800 (light mode)**
  - `screenshot()` — verify light theme (ivory bg, dark text)

- [ ] **Step 2: Click moon icon (theme toggle)**
  - Find and click the theme toggle button
  - `wait(1)`
  - `screenshot()` — verify dark theme:
    - Dark background (#1A1816 or similar)
    - Light text
    - Cards have dark surface
    - Logo still visible
    - Chips visible with proper contrast

- [ ] **Step 3: Toggle back to light**
  - Click sun icon
  - `wait(1)`
  - `screenshot()` — verify light theme restored

- [ ] **Step 4: Log results**

---

### Task 10: Accent Color Picker (Desktop)

**Target:** Desktop topbar palette icon at 1280x800

- [ ] **Step 1: Click palette icon**
  - Find and click the accent color picker button
  - `screenshot()` — verify popover with 6 color circles

- [ ] **Step 2: Click "Sunset" (orange) accent**
  - Click the orange circle
  - `wait(1)`
  - `screenshot()` — verify primary color changed to orange:
    - "New Chat" button is orange
    - Active nav tab uses orange
    - "For You" chip... (may not change since it uses --text)

- [ ] **Step 3: Reset to default (Indigo)**
  - Open palette, click first circle (blue/indigo)
  - `wait(1)` — verify blue primary restored

- [ ] **Step 4: Log results**

---

## Phase 5: Desktop Navigation

### Task 11: Desktop Topbar Navigation

**Target:** All nav tabs at 1280x800

- [ ] **Step 1: Click "Saved" tab**
  - `wait(2)`, `screenshot()` — verify `/saved` page loads

- [ ] **Step 2: Click "Ask" tab**
  - `wait(2)`, `screenshot()` — verify `/chat?new=1` loads with fresh chat

- [ ] **Step 3: Click "Compare" tab**
  - `wait(2)`, `screenshot()` — verify `/compare` page loads

- [ ] **Step 4: Click "Discover" tab**
  - `wait(2)`, `screenshot()` — verify homepage loads

- [ ] **Step 5: Click "New Chat" button**
  - `wait(2)`, `screenshot()` — verify fresh chat page

- [ ] **Step 6: Log results**

---

## Phase 6: Static & Info Pages

### Task 12: Static Pages (Desktop)

**Target:** Footer links at 1280x800

- [ ] **Step 1: Navigate to `/privacy`**
  - `screenshot()` — verify privacy policy content renders, topbar present

- [ ] **Step 2: Navigate to `/terms`**
  - `screenshot()` — verify terms of service content renders

- [ ] **Step 3: Navigate to `/affiliate-disclosure`**
  - `screenshot()` — verify affiliate disclosure content renders

- [ ] **Step 4: Navigate to `/saved`**
  - `screenshot()` — verify saved page renders (even if "coming soon")

- [ ] **Step 5: Navigate to `/compare`**
  - `screenshot()` — verify compare page renders (even if "coming soon")

- [ ] **Step 6: Log results**

---

## Phase 7: Responsive Breakpoints

### Task 13: Tablet Viewport (768x1024)

**Target:** Homepage at 768x1024

- [ ] **Step 1: Set viewport 768x1024, navigate to homepage**
  - `screenshot()` — verify:
    - No layout breakage
    - Content readable
    - No overlapping elements
    - Sidebar may or may not be visible (breakpoint dependent)

- [ ] **Step 2: Navigate to `/chat`**
  - `screenshot()` — verify chat renders correctly at tablet size

- [ ] **Step 3: Log results**

---

## Phase 8: Error States & Edge Cases

### Task 14: 404 Page

**Target:** Non-existent route

- [ ] **Step 1: Navigate to `https://www.reviewguide.ai/nonexistent-page`**
  - `screenshot()` — verify a 404 page renders (not a blank screen or crash)

- [ ] **Step 2: Log results**

---

### Task 15: Chat Welcome Screen (New Session)

**Target:** Fresh chat with no history

- [ ] **Step 1: Navigate to `/chat?new=1` at 390x844**
  - `wait(3)`
  - `screenshot()` — verify welcome screen:
    - Animated cycling verb (or static welcome)
    - Chat input visible
    - No stale messages from previous session

- [ ] **Step 2: Same at 1280x800**
  - `screenshot()` — verify desktop split-pane welcome state
  - Results panel should show "Ask a question to see results here"

- [ ] **Step 3: Log results**

---

## Results Summary Template

After all tasks complete, compile:

```markdown
## GUI QA Results — YYYY-MM-DD

### Pass/Fail Summary
| Task | Page | Viewport | Result | Notes |
|------|------|----------|--------|-------|
| 1 | Homepage | Mobile | PASS/FAIL | ... |
| 2 | Homepage | Desktop | PASS/FAIL | ... |
| ... | ... | ... | ... | ... |

### Issues Found
1. [Component] — [Description] — [Severity: Critical/Medium/Low]
2. ...

### Screenshots
- All screenshots saved with IDs for reference
```
