# Gemini Design Review Prompt

Copy everything below this line into Gemini 2.5 Pro via Antigravity.

---

You are a senior product designer and frontend architect. I need your design expertise on ReviewGuide.ai — an AI-powered product research and price comparison platform.

## Live Site
The site is live at https://www.reviewguide.ai — please visit it and review the current state.

## The Figma Design Concept (full HTML below)

This is a Figma-exported HTML mockup showing a 3-screen user flow: Discover (mobile) → Chat (mobile) → Results (desktop). Render this HTML in your mind or a browser to see the design:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ReviewGuide.ai — New UX Concept</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
  :root {
    --bg: #FAFAF7; --bg-dark: #1A1816; --surface: #FFFFFF; --surface-elevated: #F5F4F0;
    --text: #1A1816; --text-secondary: #6B6560; --text-muted: #9B9590;
    --primary: #1B4DFF; --primary-soft: rgba(27, 77, 255, 0.08); --accent: #E85D3A;
    --border: #E8E6E1; --border-strong: #D4D1CC;
    --radius: 16px; --radius-sm: 10px; --radius-xs: 6px;
    --shadow-card: 0 1px 3px rgba(26,24,22,0.06), 0 4px 12px rgba(26,24,22,0.04);
    --shadow-elevated: 0 4px 16px rgba(26,24,22,0.08), 0 12px 40px rgba(26,24,22,0.06);
    --font-body: 'DM Sans', system-ui, sans-serif;
    --font-serif: 'Instrument Serif', Georgia, serif;
  }
  body { font-family: var(--font-body); background: var(--bg); color: var(--text); line-height: 1.5; }
  .screen-flow { display: flex; gap: 80px; padding: 60px 80px; overflow-x: auto; min-height: 100vh; align-items: flex-start; }
  .screen-wrapper { flex-shrink: 0; display: flex; flex-direction: column; gap: 16px; }
  .screen-label { font-size: 11px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted); }
  .screen-label span { color: var(--primary); }
  .phone-frame { width: 390px; height: 844px; background: var(--bg); border-radius: 44px; border: 3px solid var(--border-strong); overflow: hidden; box-shadow: var(--shadow-elevated); }
  .desktop-frame { width: 1120px; height: 780px; background: var(--bg); border-radius: 12px; border: 2px solid var(--border-strong); overflow: hidden; box-shadow: var(--shadow-elevated); }
  .flow-arrow { display: flex; align-items: center; align-self: center; color: var(--text-muted); font-size: 28px; margin: 0 -40px; flex-shrink: 0; }

  /* HOME */
  .home-screen { display: flex; flex-direction: column; height: 100%; }
  .home-status-bar { display: flex; justify-content: space-between; padding: 14px 24px 8px; font-size: 13px; font-weight: 600; }
  .home-header { padding: 8px 24px 0; display: flex; justify-content: space-between; align-items: center; }
  .home-logo { font-family: var(--font-serif); font-size: 22px; font-style: italic; }
  .home-avatar { width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), #6366f1); display: flex; align-items: center; justify-content: center; color: white; font-size: 13px; font-weight: 600; }
  .home-hero { padding: 32px 24px 24px; }
  .home-hero h1 { font-family: var(--font-serif); font-size: 32px; font-weight: 400; line-height: 1.15; }
  .home-hero h1 em { font-style: italic; color: var(--primary); }
  .home-hero p { font-size: 14px; color: var(--text-secondary); margin-top: 8px; }
  .home-search { margin: 0 24px; display: flex; align-items: center; gap: 12px; background: var(--surface); border: 1.5px solid var(--border); border-radius: 14px; padding: 14px 16px; box-shadow: var(--shadow-card); }
  .home-search .search-icon, .home-search .search-text { color: var(--text-muted); }
  .home-search .mic-icon { margin-left: auto; color: var(--primary); }
  .home-chips { display: flex; gap: 8px; padding: 16px 24px; overflow-x: auto; }
  .home-chip { flex-shrink: 0; padding: 8px 14px; border-radius: 20px; font-size: 13px; font-weight: 500; background: var(--surface); border: 1px solid var(--border); color: var(--text-secondary); }
  .home-chip.active { background: var(--text); color: var(--bg); border-color: var(--text); }
  .home-section-title { padding: 8px 24px 12px; font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-muted); }
  .home-cards { padding: 0 24px; display: flex; flex-direction: column; gap: 12px; }
  .home-card { display: flex; gap: 14px; background: var(--surface); border-radius: var(--radius-sm); padding: 14px; box-shadow: var(--shadow-card); align-items: center; }
  .home-card-img { width: 56px; height: 56px; border-radius: 12px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 24px; }
  .home-card-text h3 { font-size: 14px; font-weight: 600; margin-bottom: 2px; }
  .home-card-text p { font-size: 12px; color: var(--text-secondary); }
  .home-card-arrow { margin-left: auto; color: var(--text-muted); }

  /* BOTTOM NAV */
  .bottom-nav { margin-top: auto; display: flex; justify-content: space-around; align-items: center; padding: 10px 0 28px; background: var(--surface); border-top: 1px solid var(--border); }
  .nav-item { display: flex; flex-direction: column; align-items: center; gap: 4px; font-size: 10px; color: var(--text-muted); font-weight: 500; }
  .nav-item.active { color: var(--primary); }
  .nav-fab { width: 52px; height: 52px; border-radius: 50%; background: var(--primary); color: white; display: flex; align-items: center; justify-content: center; font-size: 24px; box-shadow: 0 4px 16px rgba(27, 77, 255, 0.35); margin-top: -28px; }

  /* CHAT */
  .chat-screen { display: flex; flex-direction: column; height: 100%; }
  .chat-header { display: flex; align-items: center; gap: 12px; padding: 14px 20px 12px; border-bottom: 1px solid var(--border); background: var(--surface); }
  .chat-header .back-btn { font-size: 20px; color: var(--text-secondary); }
  .chat-header-info h3 { font-size: 15px; font-weight: 600; }
  .chat-header-info p { font-size: 11px; color: var(--text-muted); }
  .chat-messages { flex: 1; padding: 20px; display: flex; flex-direction: column; gap: 16px; overflow-y: auto; }
  .msg { max-width: 85%; padding: 12px 16px; border-radius: 18px; font-size: 14px; line-height: 1.5; }
  .msg-user { align-self: flex-end; background: var(--primary); color: white; border-bottom-right-radius: 6px; }
  .msg-ai { align-self: flex-start; background: var(--surface); border: 1px solid var(--border); border-bottom-left-radius: 6px; }
  .msg-ai .ai-label { font-size: 11px; font-weight: 600; color: var(--primary); margin-bottom: 4px; }
  .typing-indicator { display: flex; gap: 4px; padding: 12px 16px; align-self: flex-start; background: var(--surface); border: 1px solid var(--border); border-radius: 18px; border-bottom-left-radius: 6px; }
  .typing-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--text-muted); animation: typing 1.2s infinite; }
  .typing-dot:nth-child(2) { animation-delay: 0.15s; }
  .typing-dot:nth-child(3) { animation-delay: 0.3s; }
  @keyframes typing { 0%, 60%, 100% { opacity: 0.3; transform: translateY(0); } 30% { opacity: 1; transform: translateY(-3px); } }
  .chat-suggestions { display: flex; gap: 8px; padding: 0 20px 8px; overflow-x: auto; }
  .chat-suggestion { flex-shrink: 0; padding: 8px 14px; border-radius: 20px; font-size: 12px; font-weight: 500; background: var(--primary-soft); color: var(--primary); }
  .chat-input-bar { display: flex; align-items: center; gap: 10px; padding: 12px 16px 32px; background: var(--surface); border-top: 1px solid var(--border); }
  .chat-input-field { flex: 1; padding: 10px 16px; border-radius: 24px; border: 1.5px solid var(--border); font-size: 14px; background: var(--bg); color: var(--text-muted); }
  .chat-send-btn { width: 40px; height: 40px; border-radius: 50%; background: var(--primary); color: white; display: flex; align-items: center; justify-content: center; font-size: 18px; }

  /* RESULTS */
  .results-screen { display: flex; height: 100%; }
  .results-sidebar { width: 320px; border-right: 1px solid var(--border); background: var(--surface); display: flex; flex-direction: column; }
  .results-sidebar-header { padding: 20px 20px 16px; border-bottom: 1px solid var(--border); }
  .results-sidebar-header .logo { font-family: var(--font-serif); font-size: 20px; font-style: italic; margin-bottom: 16px; }
  .results-sidebar-search { display: flex; align-items: center; gap: 8px; padding: 10px 14px; background: var(--bg); border-radius: var(--radius-xs); border: 1px solid var(--border); font-size: 13px; color: var(--text-muted); }
  .results-chat-list { flex: 1; padding: 12px; display: flex; flex-direction: column; gap: 4px; }
  .results-chat-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: var(--radius-xs); font-size: 13px; color: var(--text-secondary); }
  .results-chat-item.active { background: var(--primary-soft); color: var(--primary); font-weight: 500; }
  .results-main { flex: 1; display: flex; flex-direction: column; overflow-y: auto; }
  .results-topbar { display: flex; align-items: center; justify-content: space-between; padding: 16px 28px; border-bottom: 1px solid var(--border); background: var(--surface); position: sticky; top: 0; }
  .results-topbar h2 { font-family: var(--font-serif); font-size: 20px; font-weight: 400; font-style: italic; }
  .results-topbar-btn { padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 500; background: var(--surface-elevated); color: var(--text-secondary); border: 1px solid var(--border); }
  .results-content { padding: 28px; display: flex; flex-direction: column; gap: 20px; }
  .results-summary { font-size: 14px; line-height: 1.7; color: var(--text-secondary); max-width: 680px; }
  .results-summary strong { color: var(--text); font-weight: 600; }
  .product-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
  .product-card { background: var(--surface); border-radius: var(--radius); border: 1px solid var(--border); overflow: hidden; box-shadow: var(--shadow-card); transition: box-shadow 0.2s, transform 0.2s; }
  .product-card:hover { box-shadow: var(--shadow-elevated); transform: translateY(-2px); }
  .product-card-image { height: 140px; display: flex; align-items: center; justify-content: center; font-size: 48px; background: var(--surface-elevated); }
  .product-card-rank { position: absolute; top: 12px; left: 12px; width: 28px; height: 28px; border-radius: 50%; background: var(--text); color: var(--bg); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; }
  .product-card-body { padding: 16px; }
  .product-card-body .badge { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
  .badge-top { background: #FEF3C7; color: #92400E; }
  .badge-value { background: #DBEAFE; color: #1E40AF; }
  .badge-premium { background: #F3E8FF; color: #6B21A8; }
  .product-card-body h3 { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
  .product-card-body .product-meta { font-size: 12px; color: var(--text-muted); margin-bottom: 10px; }
  .score-bar { flex: 1; height: 4px; border-radius: 2px; background: var(--surface-elevated); }
  .score-fill { height: 100%; border-radius: 2px; background: var(--primary); }
  .score-label { font-size: 13px; font-weight: 700; color: var(--primary); }
  .product-card-footer { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-top: 1px solid var(--border); }
  .product-price { font-size: 16px; font-weight: 700; }
  .product-cta { padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600; background: var(--primary); color: white; }
  .results-panel { width: 320px; border-left: 1px solid var(--border); background: var(--surface); padding: 20px; display: flex; flex-direction: column; gap: 20px; }
  .panel-section h4 { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); margin-bottom: 12px; }
  .panel-source { display: flex; align-items: center; gap: 10px; padding: 8px 0; font-size: 13px; color: var(--text-secondary); border-bottom: 1px solid var(--border); }
  .source-dot { width: 8px; height: 8px; border-radius: 50%; }
  .quick-action { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: var(--radius-xs); background: var(--bg); font-size: 13px; color: var(--text-secondary); }
  .quick-action:hover { background: var(--primary-soft); color: var(--primary); }
  .page-title { text-align: center; padding: 0 0 20px; }
  .page-title h1 { font-family: var(--font-serif); font-size: 42px; font-weight: 400; font-style: italic; margin-bottom: 8px; }
  .page-title h1 span { color: var(--primary); }
  .page-title p { font-size: 16px; color: var(--text-secondary); max-width: 500px; margin: 0 auto; }
</style>
</head>
<body>
<div class="page-title">
  <h1>ReviewGuide.<span>ai</span> — New UX</h1>
  <p>Editorial sophistication meets app-like fluidity. Discover → Chat → Results.</p>
</div>
<div class="screen-flow">
  <!-- SCREEN 1: DISCOVER -->
  <div class="screen-wrapper">
    <div class="screen-label"><span>01</span> — Discover</div>
    <div class="phone-frame">
      <div class="home-screen">
        <div class="home-status-bar"><span class="time">9:41</span><span class="icons">●●● ▮▮▮ 🔋</span></div>
        <div class="home-header"><div class="home-logo">ReviewGuide</div><div class="home-avatar">HJ</div></div>
        <div class="home-hero"><h1>What are you<br><em>researching</em> today?</h1><p>Expert reviews, real data, zero fluff.</p></div>
        <div class="home-search"><span class="search-icon">🔍</span><span class="search-text">Best noise-cancelling headphones...</span><span class="mic-icon">🎤</span></div>
        <div class="home-chips"><div class="home-chip active">For You</div><div class="home-chip">Tech</div><div class="home-chip">Travel</div><div class="home-chip">Kitchen</div><div class="home-chip">Fitness</div><div class="home-chip">Audio</div></div>
        <div class="home-section-title">Trending Research</div>
        <div class="home-cards">
          <div class="home-card"><div class="home-card-img" style="background: linear-gradient(135deg, #DBEAFE, #BFDBFE);">🎧</div><div class="home-card-text"><h3>Best Headphones 2026</h3><p>Sony vs Bose vs Apple — expert verdict</p></div><span class="home-card-arrow">›</span></div>
          <div class="home-card"><div class="home-card-img" style="background: linear-gradient(135deg, #FEF3C7, #FDE68A);">✈️</div><div class="home-card-text"><h3>Tokyo on a Budget</h3><p>7-day itinerary under $2,000</p></div><span class="home-card-arrow">›</span></div>
          <div class="home-card"><div class="home-card-img" style="background: linear-gradient(135deg, #F3E8FF, #E9D5FF);">💻</div><div class="home-card-text"><h3>M4 MacBook vs ThinkPad</h3><p>For developers who mean business</p></div><span class="home-card-arrow">›</span></div>
        </div>
        <div class="bottom-nav">
          <div class="nav-item active"><span class="nav-icon">🏠</span>Discover</div>
          <div class="nav-item"><span class="nav-icon">🔖</span>Saved</div>
          <div class="nav-fab">✦</div>
          <div class="nav-item"><span class="nav-icon">📊</span>Compare</div>
          <div class="nav-item"><span class="nav-icon">👤</span>Profile</div>
        </div>
      </div>
    </div>
  </div>
  <div class="flow-arrow">→</div>
  <!-- SCREEN 2: CHAT -->
  <div class="screen-wrapper">
    <div class="screen-label"><span>02</span> — Chat</div>
    <div class="phone-frame">
      <div class="chat-screen">
        <div class="home-status-bar"><span class="time">9:42</span><span class="icons">●●● ▮▮▮ 🔋</span></div>
        <div class="chat-header"><span class="back-btn">‹</span><div class="chat-header-info"><h3>Best Headphones 2026</h3><p>Researching • 4 sources analyzed</p></div><span class="share-btn">↗</span></div>
        <div class="chat-messages">
          <div class="msg msg-user">What are the best noise-cancelling headphones for commuting?</div>
          <div class="msg msg-ai"><div class="ai-label">✦ ReviewGuide</div>Based on <strong>147 expert reviews</strong> and real-world testing data, here are the top picks for commuting:<br><br>The <strong>Sony WH-1000XM6</strong> leads for noise cancellation, while the <strong>Bose QC Ultra</strong> edges ahead on comfort.<br><br>Let me pull up the detailed comparison...</div>
          <div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>
        </div>
        <div class="chat-suggestions"><div class="chat-suggestion">Compare top 3</div><div class="chat-suggestion">Under $300</div><div class="chat-suggestion">Best for calls</div><div class="chat-suggestion">Wireless range</div></div>
        <div class="chat-input-bar"><div class="chat-input-field">Ask a follow-up...</div><div class="chat-send-btn">↑</div></div>
      </div>
    </div>
  </div>
  <div class="flow-arrow">→</div>
  <!-- SCREEN 3: RESULTS (Desktop) -->
  <div class="screen-wrapper">
    <div class="screen-label"><span>03</span> — Results</div>
    <div class="desktop-frame">
      <div class="results-screen">
        <div class="results-sidebar">
          <div class="results-sidebar-header"><div class="logo">ReviewGuide</div><div class="results-sidebar-search">🔍 Search conversations...</div></div>
          <div class="results-chat-list">
            <div class="results-chat-item active"><span class="item-icon">🎧</span>Best Headphones 2026</div>
            <div class="results-chat-item"><span class="item-icon">✈️</span>Tokyo Trip Planning</div>
            <div class="results-chat-item"><span class="item-icon">💻</span>Laptop for Development</div>
            <div class="results-chat-item"><span class="item-icon">📷</span>Mirrorless Camera Guide</div>
            <div class="results-chat-item"><span class="item-icon">🏃</span>Running Shoes Comparison</div>
          </div>
        </div>
        <div class="results-main">
          <div class="results-topbar"><h2>Best Noise-Cancelling Headphones</h2><div class="results-topbar-actions"><div class="results-topbar-btn">↗ Share</div><div class="results-topbar-btn">🔖 Save</div><div class="results-topbar-btn">⟳ Refresh</div></div></div>
          <div class="results-content">
            <div class="results-summary">After analyzing <strong>147 expert reviews</strong> across Wirecutter, RTINGS, SoundGuys, and 6 other sources, here are the top noise-cancelling headphones. Rankings factor in <strong>ANC performance</strong>, <strong>comfort</strong>, <strong>battery life</strong>, and <strong>value</strong>.</div>
            <div class="product-grid">
              <div class="product-card" style="position:relative;"><div class="product-card-image" style="background:linear-gradient(135deg,#EEF2FF,#E0E7FF);">🎧</div><div class="product-card-rank">1</div><div class="product-card-body"><span class="badge badge-top">Top Pick</span><h3>Sony WH-1000XM6</h3><p class="product-meta">Best noise cancellation overall</p><div class="product-score"><div class="score-bar"><div class="score-fill" style="width:94%;"></div></div><span class="score-label">9.4</span></div></div><div class="product-card-footer"><span class="product-price">$348</span><span class="product-cta">Check Price</span></div></div>
              <div class="product-card" style="position:relative;"><div class="product-card-image" style="background:linear-gradient(135deg,#FEF3C7,#FDE68A);">🎧</div><div class="product-card-rank">2</div><div class="product-card-body"><span class="badge badge-value">Best Value</span><h3>Bose QC Ultra</h3><p class="product-meta">Most comfortable for long wear</p><div class="product-score"><div class="score-bar"><div class="score-fill" style="width:91%;"></div></div><span class="score-label">9.1</span></div></div><div class="product-card-footer"><span class="product-price">$329</span><span class="product-cta">Check Price</span></div></div>
              <div class="product-card" style="position:relative;"><div class="product-card-image" style="background:linear-gradient(135deg,#F3E8FF,#E9D5FF);">🎧</div><div class="product-card-rank">3</div><div class="product-card-body"><span class="badge badge-premium">Premium</span><h3>Apple AirPods Max 2</h3><p class="product-meta">Best Apple ecosystem integration</p><div class="product-score"><div class="score-bar"><div class="score-fill" style="width:88%;"></div></div><span class="score-label">8.8</span></div></div><div class="product-card-footer"><span class="product-price">$549</span><span class="product-cta">Check Price</span></div></div>
            </div>
          </div>
        </div>
        <div class="results-panel">
          <div class="panel-section"><h4>Sources Analyzed</h4>
            <div class="panel-source"><div class="source-dot" style="background:#EF4444;"></div>Wirecutter — "Best Headphones 2026"</div>
            <div class="panel-source"><div class="source-dot" style="background:#3B82F6;"></div>RTINGS — Lab Measurements</div>
            <div class="panel-source"><div class="source-dot" style="background:#10B981;"></div>SoundGuys — Field Testing</div>
            <div class="panel-source"><div class="source-dot" style="background:#F59E0B;"></div>Head-Fi — Community Reviews</div>
            <div class="panel-source"><div class="source-dot" style="background:#8B5CF6;"></div>+5 more sources</div>
          </div>
          <div class="panel-section"><h4>Quick Actions</h4>
            <div class="panel-quick-actions">
              <div class="quick-action">📊 Compare side by side</div>
              <div class="quick-action">💰 Set price alert</div>
              <div class="quick-action">📋 Export to list</div>
              <div class="quick-action">🔗 Share results</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
</body>
</html>
```

## What's Currently Built (v3 — live on the site now)

Recent changes that may differ from the Figma:
- **Dark mode default** (#0C0E14 blue-black) instead of Figma's light cream (#FAFAF7)
- **Chat-centric UX** — no separate Results page; products render inline in chat
- **Sidebar on homepage** instead of category chips
- **No floating FAB** "Ask" button in mobile nav
- **No 3-column results layout** (left sidebar + product grid + sources panel)
- **No product card grid** with rank badges, score bars, gradient image areas
- **Themed accent picker** (Ocean, Sunset, Neon, Forest, Berry)
- **Streaming improvements** (pulsing dots, stop button, cursor)
- **Gradient buy buttons** on product cards

## What I Need

Be opinionated. Think like a design lead at Stripe or Airbnb reviewing this before launch.

### 1. Design Direction Verdict
Should we pursue the Figma's light-mode-first, 3-screen Discover→Chat→Results architecture? Or keep the current dark-mode-first, chat-centric approach? Consider:
- Which feels more trustworthy for product recommendations?
- Which differentiates from Amazon, Wirecutter, Perplexity?
- Which works better for a chat-based AI product?

### 2. Top 5 Elements to Adopt from the Figma
Highest-impact design elements to implement, ranked.

### 3. What to Keep from v3
What should survive even if we go with the Figma direction?

### 4. What to Skip or Modify
Elements in the Figma that feel wrong, impractical, or would hurt UX.

### 5. Actionable Implementation Priority
Ordered list of changes, highest to lowest impact. Be specific about components and layouts.

### 6. Dark Mode vs Light Mode
The Figma is light-first. We shipped dark-first. Which should be default for a shopping/reviews product? Can both work well?
