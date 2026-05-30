// Discover, Chat (empty / fast / quiz / loading) screens.

const { color: c, font: f, radius: r, shadow: s } = window.RG;

// ============================================================
// 01. DISCOVER (home)
// ============================================================
function DiscoverScreen() {
  const trending = [
    { topic: 'Wireless earbuds under $100', tag: 'Audio' },
    { topic: 'Tokyo hotels for cherry blossom',   tag: 'Travel' },
    { topic: 'Laptops for design work, $1500',    tag: 'Tech' },
    { topic: 'A pizza oven for a small balcony',  tag: 'Kitchen' },
    { topic: 'Running shoes for marathon training', tag: 'Fitness' },
  ];
  const popular = [
    { name: 'Bose QC Ultra',     take: 'Most-asked-about ANC pick this month.',  price: '$429', tint: '#C5B7A2' },
    { name: 'Sony WH-1000XM5',   take: 'Still the all-rounder if calls aren’t central.', price: '$399', tint: '#B7BFC5' },
    { name: 'Hoshinoya Kyoto',   take: 'The ryokan-resort people end up writing essays about.', price: '$1,180/nt', tint: '#CFC8B8' },
  ];
  const recent = [
    { topic: 'Wireless headphones for commute',
      last: 'You’re on the right track \u2014 here’s the one catch.',
      when: '2h' },
    { topic: 'A standing desk under $500',
      last: 'The Jarvis edges Uplift on warranty terms.',
      when: 'Yesterday' },
  ];

  return (
    <Phone label="Discover" height={1240}>
      <div style={{ padding: '4px 22px 110px' }}>

        {/* Discover hero — the one place the bubble exists in the product */}
        <div style={{
          display: 'flex', justifyContent: 'center',
          padding: '12px 0 28px',
        }}>
          <LogoHero rotate width={300} />
        </div>

        {/* Greeting — editorial; now smaller, sits beneath the bubble */}
        <h1 style={{
          margin: 0, fontFamily: f.display, fontStyle: 'italic',
          fontSize: 28, lineHeight: '32px', letterSpacing: '-0.02em',
          color: c.ink, fontWeight: 400, marginBottom: 14,
          textAlign: 'left',
        }}>What are you researching?</h1>

        {/* Prompt input — tappable */}
        <div style={{
          padding: '14px 14px 14px 18px',
          background: c.paperHi, border: `1px solid ${c.line2}`,
          borderRadius: 16, display: 'flex', alignItems: 'center', gap: 8,
          boxShadow: s.card,
        }}>
          <span style={{
            flex: 1, fontFamily: f.sans, fontSize: 15, color: c.ink3,
          }}>Ask about anything you’re weighing…</span>
          <span style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            width: 8, height: 18, background: c.terra,
            animation: 'rg-breath 1.6s ease-in-out infinite',
          }}/>
        </div>

        {/* Trending right now */}
        <div style={{ marginTop: 28 }}>
          <Eyebrow>Trending right now</Eyebrow>
          <div style={{
            display: 'flex', gap: 8, overflowX: 'auto',
            margin: '0 -22px', padding: '4px 22px 8px',
          }}>
            {trending.map((t, i) => (
              <div key={i} style={{
                flex: '0 0 auto',
                padding: '12px 14px', maxWidth: 260,
                background: c.paperHi, border: `1px solid ${c.line}`,
                borderRadius: 12,
                display: 'flex', flexDirection: 'column', gap: 4,
              }}>
                <span style={{
                  fontFamily: f.sans, fontSize: 9, fontWeight: 600,
                  letterSpacing: '0.10em', textTransform: 'uppercase',
                  color: c.ink3,
                }}>{t.tag}</span>
                <span style={{
                  fontFamily: f.sans, fontSize: 14, lineHeight: '20px', color: c.ink,
                  whiteSpace: 'nowrap',
                }}>{t.topic}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Popular this week */}
        <div style={{ marginTop: 28 }}>
          <Eyebrow action="See all">Popular this week</Eyebrow>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {popular.map((p, i) => (
              <div key={i} style={{
                display: 'flex', gap: 14, alignItems: 'center',
                padding: '12px 0',
                borderBottom: i === popular.length - 1 ? 'none' : `1px solid ${c.line}`,
              }}>
                <div style={{
                  width: 64, height: 64, borderRadius: 10,
                  overflow: 'hidden', position: 'relative', flex: '0 0 64px',
                }}>
                  <PlaceholderProduct tint={p.tint} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontFamily: f.serif, fontSize: 17, lineHeight: '22px',
                    color: c.ink, fontWeight: 500, letterSpacing: '-0.01em',
                    marginBottom: 2,
                  }}>{p.name}</div>
                  <div style={{
                    fontFamily: f.sans, fontSize: 12, lineHeight: '17px',
                    color: c.ink2,
                  }}>{p.take}</div>
                </div>
                <div style={{
                  fontFamily: f.sans, fontSize: 13, color: c.ink, fontWeight: 500,
                  whiteSpace: 'nowrap',
                }}>{p.price}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent chats — pick up where you left off */}
        <div style={{ marginTop: 28 }}>
          <Eyebrow>Pick up where you left off</Eyebrow>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {recent.map((r, i) => (
              <div key={i} style={{
                padding: '14px 16px',
                background: c.paperHi, border: `1px solid ${c.line}`,
                borderRadius: 12,
              }}>
                <div style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  marginBottom: 6,
                }}>
                  <span style={{
                    fontFamily: f.sans, fontSize: 14, fontWeight: 500, color: c.ink,
                  }}>{r.topic}</span>
                  <span style={{ fontFamily: f.sans, fontSize: 11, color: c.ink3 }}>{r.when}</span>
                </div>
                <div style={{
                  fontFamily: f.display, fontStyle: 'italic', fontSize: 15,
                  lineHeight: '20px', color: c.ink2,
                }}>“{r.last}”</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <TabBar active="discover" />
    </Phone>
  );
}

// ============================================================
// 02. CHAT — EMPTY
// ============================================================
function ChatEmptyScreen() {
  const starters = [
    'Wireless earbuds under $100',
    'A laptop that won’t embarrass me on Zoom',
    'Tokyo hotels for cherry blossom week',
    'A pizza oven that fits a small balcony',
  ];
  return (
    <Phone label="Chat — empty" height={844}>
      <HeaderBrand back />

      <div style={{ padding: '24px 22px 0' }}>
        <div style={{
          fontFamily: f.display, fontStyle: 'italic',
          fontSize: 30, lineHeight: '34px', letterSpacing: '-0.02em',
          color: c.ink, marginBottom: 14,
        }}>What are you trying to figure out?</div>
        <div style={{ fontFamily: f.sans, fontSize: 14, color: c.ink2, lineHeight: '20px' }}>
          A category, a budget, a vibe — anything works.
        </div>
      </div>

      <div style={{ padding: '32px 22px 0' }}>
        <Eyebrow>A few people are asking</Eyebrow>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {starters.map((t, i) => (
            <Chip key={i} full>{t}</Chip>
          ))}
        </div>
      </div>

      <Composer placeholder="Type anything… or tap above" />
    </Phone>
  );
}

// ============================================================
// 03. CHAT — FAST PATH (mid-loading)
// ============================================================
function ChatFastScreen() {
  return (
    <Phone label="Chat — fast path · loading" height={844}>
      <HeaderBrand back context="Wireless earbuds" right={
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <circle cx="5" cy="12" r="1.5" fill={c.ink2}/>
          <circle cx="12" cy="12" r="1.5" fill={c.ink2}/>
          <circle cx="19" cy="12" r="1.5" fill={c.ink2}/>
        </svg>
      }/>

      <div style={{ padding: '8px 22px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <UserBubble>Best wireless earbuds under $100?</UserBubble>
        <LoadingBubble text="Sorting the contenders…"/>
      </div>

      <Composer placeholder="Reply with anything" disabled />
    </Phone>
  );
}

// ============================================================
// 04. CHAT — QUIZ PATH
// ============================================================
function ChatQuizScreen() {
  return (
    <Phone label="Chat — quiz path" height={920}>
      <HeaderBrand back context="A new laptop" />

      <div style={{
        padding: '8px 22px 0', display: 'flex', flexDirection: 'column', gap: 16,
        overflow: 'hidden',
      }}>
        <UserBubble>I need a new laptop.</UserBubble>

        <AIBubble>
          <p style={{ margin: 0 }}>
            Happy to narrow this — "best laptop" changes a lot based on what you’re doing with it. A few questions:
          </p>
        </AIBubble>

        <UserBubble>Code and the occasional Lightroom session.</UserBubble>

        <AIBubble style={{ maxWidth: 320 }}>
          <p style={{ margin: 0, marginBottom: 12 }}>
            Got it. <span style={{ color: c.ink2 }}>1 of 3 ·</span> what’s the rough budget?
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Chip leadingDot>Under $1,200</Chip>
            <Chip leadingDot accent>$1,200 – $1,800</Chip>
            <Chip leadingDot>$1,800 – $2,500</Chip>
            <Chip leadingDot>No firm ceiling</Chip>
          </div>
          <div style={{
            marginTop: 12, fontFamily: f.sans, fontSize: 12, color: c.ink3,
          }}>or just type if none of these quite fit.</div>
        </AIBubble>
      </div>

      <Composer placeholder="Type a reply…" />
    </Phone>
  );
}

Object.assign(window, { DiscoverScreen, ChatEmptyScreen, ChatFastScreen, ChatQuizScreen });
