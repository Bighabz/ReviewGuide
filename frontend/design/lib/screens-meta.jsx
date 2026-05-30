// Saved, Compare, Personality Profile, Loading-detail.

const { color: mc, font: mf, radius: mr, shadow: ms } = window.RG;

// ============================================================
// 07. LOADING (close-up, in-context)
// ============================================================
function LoadingScreen() {
  return (
    <Phone label="Loading state" height={844}>
      <HeaderBrand back context="Kyoto hotels" />

      <div style={{ padding: '8px 22px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <UserBubble>Looking at hotels in Kyoto for a week in April.</UserBubble>
        <LoadingBubble text="Reading the room…"/>
      </div>

      {/* Annotation overlay — rotation */}
      <div style={{
        position: 'absolute', left: 22, right: 22, bottom: 140,
        padding: 14,
        background: mc.paperHi, border: `1px solid ${mc.line}`,
        borderRadius: 12,
      }}>
        <div className="rg-eyebrow" style={{ marginBottom: 6 }}>Rotates every ~2s</div>
        <div style={{
          display: 'flex', flexDirection: 'column', gap: 4,
          fontFamily: mf.display, fontStyle: 'italic',
          fontSize: 14, lineHeight: '20px', color: mc.ink2,
        }}>
          <span>“Reading the room…”</span>
          <span style={{ opacity: .5 }}>“Cross-checking the specs…”</span>
          <span style={{ opacity: .3 }}>“Hunting for the catch…”</span>
        </div>
      </div>

      <Composer placeholder="Reply with anything" disabled />
    </Phone>
  );
}

// ============================================================
// 08. SAVED
// ============================================================
function SavedScreen() {
  const items = [
    { name: 'Bose QC Ultra',     label: 'Top pick · headphones, June',  price: '$429', tint: '#C5B7A2', selected: true },
    { name: 'Sonos Ace',         label: 'Budget pick · headphones',     price: '$349', tint: '#CFC8B8', selected: true },
    { name: 'Hoshinoya Kyoto',   label: 'Top pick · April trip',        price: '$1,180/nt', tint: '#D8C8B0' },
    { name: 'Jarvis Bamboo',     label: 'Standing desk · still deciding', price: '$579', tint: '#B7A98B' },
    { name: 'Nothing Ear (a)',   label: 'Looks pick · earbuds',         price: '$99',  tint: '#C9C5BD' },
    { name: 'Hoka Clifton 9',    label: 'Daily trainer · marathon',     price: '$145', tint: '#BFB6A4' },
  ];
  return (
    <Phone label="Saved" height={1120}>
      <HeaderBrand back={false} context="Things you bookmarked" />

      <div style={{ padding: '0 22px 12px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginBottom: 2, marginTop: 8,
        }}>
          <span style={{
            fontFamily: mf.sans, fontSize: 12, color: mc.ink3,
          }}>Saved on this device · 6 items</span>
          <div style={{
            padding: '6px 12px', borderRadius: 999,
            background: mc.terra, color: mc.paper,
            fontFamily: mf.sans, fontSize: 12, fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            Compare <span style={{ opacity: .8 }}>· 2</span>
          </div>
        </div>
      </div>

      <div style={{
        padding: '8px 22px 100px',
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14,
      }}>
        {items.map((it, i) => (
          <div key={i} style={{
            position: 'relative',
            background: mc.paperHi, border: `1px solid ${it.selected ? mc.terra : mc.line}`,
            borderRadius: 14, overflow: 'hidden',
          }}>
            <div style={{ position: 'relative', height: 110 }}>
              <PlaceholderProduct tint={it.tint} />
              <div style={{
                position: 'absolute', top: 8, right: 8,
                width: 28, height: 28, borderRadius: 999,
                background: 'rgba(255,255,255,.92)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Bookmark filled size={14} />
              </div>
              {it.selected && (
                <div style={{
                  position: 'absolute', top: 8, left: 8,
                  width: 22, height: 22, borderRadius: 999,
                  background: mc.terra,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                    <path d="M5 12l4 4 10-10" stroke={mc.paper} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
              )}
            </div>
            <div style={{ padding: '10px 12px 12px' }}>
              <div style={{
                fontFamily: mf.sans, fontSize: 9, fontWeight: 600,
                letterSpacing: '0.10em', textTransform: 'uppercase',
                color: mc.ink2, marginBottom: 4,
              }}>{it.label}</div>
              <div style={{
                fontFamily: mf.serif, fontSize: 15, lineHeight: '20px',
                color: mc.ink, fontWeight: 500, letterSpacing: '-0.005em',
              }}>{it.name}</div>
              <div style={{
                marginTop: 6, fontFamily: mf.sans, fontSize: 12, color: mc.ink,
                fontWeight: 500,
              }}>{it.price}</div>
            </div>
          </div>
        ))}
      </div>

      <TabBar active="saved" />
    </Phone>
  );
}

// ============================================================
// 09. COMPARE
// ============================================================
function CompareScreen() {
  const A = { name: 'Bose QC Ultra',  brand: 'Bose', price: '$429', tint: '#C5B7A2' };
  const B = { name: 'Sony WH-1000XM5', brand: 'Sony', price: '$399', tint: '#B7BFC5' };
  const rows = [
    ['ANC',     'Class-leading',         'Excellent',         'A'],
    ['Calls',   'Best-in-class mic',     'Long-standing weak point', 'A'],
    ['Comfort (glasses)', 'Gentle seal', 'Seal lifts on temples', 'A'],
    ['Sound (default tune)', 'Neutral, polite', 'Warmer, more app control', 'B'],
    ['Battery', '24 hrs',                '30 hrs',            'B'],
    ['Case',    'Bulkier',               'Slimmer for personal item', 'B'],
  ];
  return (
    <Phone label="Compare" height={1240}>
      <HeaderBrand back context="Comparing two" />

      {/* Two-column header */}
      <div style={{ padding: '0 22px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {[A, B].map((p, i) => (
          <div key={i} style={{
            background: mc.paperHi, border: `1px solid ${mc.line}`,
            borderRadius: 14, overflow: 'hidden',
          }}>
            <div style={{ position: 'relative', height: 130 }}>
              <PlaceholderProduct tint={p.tint} />
            </div>
            <div style={{ padding: '10px 12px 12px' }}>
              <div style={{
                fontFamily: mf.sans, fontSize: 9, fontWeight: 600,
                letterSpacing: '0.10em', textTransform: 'uppercase',
                color: mc.ink3, marginBottom: 4,
              }}>{p.brand}</div>
              <div style={{
                fontFamily: mf.serif, fontSize: 16, lineHeight: '20px',
                color: mc.ink, fontWeight: 500, letterSpacing: '-0.005em',
              }}>{p.name}</div>
              <div style={{
                marginTop: 4, fontFamily: mf.sans, fontSize: 13, color: mc.ink,
                fontWeight: 500,
              }}>{p.price}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Verdict */}
      <div style={{
        margin: '20px 22px 0',
        padding: '18px 18px 18px',
        background: mc.terraSoft,
        borderRadius: 14,
        border: `1px solid ${mc.terra}33`,
      }}>
        <div style={{
          fontFamily: mf.sans, fontSize: 10, fontWeight: 600,
          letterSpacing: '0.14em', textTransform: 'uppercase',
          color: mc.terraInk, marginBottom: 8,
        }}>The verdict for you</div>
        <p style={{
          margin: 0, fontFamily: mf.serif, fontSize: 17, lineHeight: '24px',
          color: mc.ink, fontWeight: 500,
        }}>
          For glasses, daily commute, and lots of calls — the <span style={{ fontWeight: 600 }}>QC Ultra</span> is the
          pick. The XM5 would be the right call if you mostly listened at home and weighted sound character over
          call quality.
        </p>
      </div>

      {/* Curated spec rows */}
      <div style={{ padding: '24px 22px 0' }}>
        <Eyebrow>What matters for you</Eyebrow>
        <div style={{ borderTop: `1px solid ${mc.line}` }}>
          {rows.map(([k, a, b, winner], i) => (
            <div key={i} style={{
              padding: '12px 0',
              borderBottom: `1px solid ${mc.line}`,
              display: 'grid', gridTemplateColumns: '1fr 1fr', columnGap: 12, rowGap: 4,
            }}>
              <div style={{ gridColumn: '1 / -1', fontFamily: mf.sans, fontSize: 11, fontWeight: 600, color: mc.ink2, letterSpacing: '0.04em', textTransform: 'uppercase' }}>{k}</div>
              <div style={{
                fontFamily: mf.serif, fontSize: 14, lineHeight: '20px',
                color: mc.ink,
                position: 'relative', paddingLeft: 10,
              }}>
                <span style={{
                  position: 'absolute', left: 0, top: 8, width: 4, height: 4, borderRadius: 999,
                  background: winner === 'A' ? mc.terra : 'transparent',
                }}/>
                {a}
              </div>
              <div style={{
                fontFamily: mf.serif, fontSize: 14, lineHeight: '20px',
                color: mc.ink,
                position: 'relative', paddingLeft: 10,
              }}>
                <span style={{
                  position: 'absolute', left: 0, top: 8, width: 4, height: 4, borderRadius: 999,
                  background: winner === 'B' ? mc.terra : 'transparent',
                }}/>
                {b}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{
        padding: '20px 22px 30px',
        display: 'flex', gap: 10,
      }}>
        <button style={{
          flex: 1, padding: '14px 0', borderRadius: 999, border: `1px solid ${mc.line2}`,
          background: mc.paperHi, color: mc.ink,
          fontFamily: mf.sans, fontSize: 14, fontWeight: 500,
        }}>Buy XM5</button>
        <button style={{
          flex: 1.6, padding: '14px 0', borderRadius: 999, border: 'none',
          background: mc.ink, color: mc.paper,
          fontFamily: mf.sans, fontSize: 14, fontWeight: 500,
        }}>Go with the QC Ultra →</button>
      </div>
    </Phone>
  );
}

// ============================================================
// 10. PERSONALITY PROFILE — "About you"
// MVP build: the empty-state version. The populated version
// (kept below as ProfileScreenFull) is the post-MVP reference.
// ============================================================
function ProfileScreen() {
  return (
    <Phone label="About you · MVP empty state" height={920}>
      <HeaderBrand back={false} />

      {/* Banner — makes the MVP deferral explicit, not buried in copy */}
      <div style={{
        margin: '0 22px',
        padding: '10px 14px',
        background: mc.terraSoft,
        border: `1px solid ${mc.terra}33`,
        borderRadius: 10,
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <span style={{
          width: 6, height: 6, borderRadius: 999, background: mc.terra,
          flex: '0 0 6px',
        }}/>
        <span style={{
          fontFamily: mf.sans, fontSize: 11, lineHeight: '16px', color: mc.terraInk,
          letterSpacing: '0.01em',
        }}>
          <strong style={{ fontWeight: 600 }}>MVP state.</strong>{' '}
          Populated personality profile deferred post-MVP — route reserved, empty-state only.
        </span>
      </div>

      <div style={{ padding: '28px 28px 0' }}>
        <div className="rg-eyebrow" style={{ marginBottom: 12 }}>About you</div>
        <h1 style={{
          margin: 0, fontFamily: mf.display, fontStyle: 'italic',
          fontSize: 38, lineHeight: '42px', letterSpacing: '-0.02em',
          color: mc.ink, fontWeight: 400,
        }}>Still getting to know you.</h1>
        <p style={{
          margin: '18px 0 0',
          fontFamily: mf.serif, fontSize: 17, lineHeight: '26px',
          color: mc.ink2, letterSpacing: '-0.005em', maxWidth: 320,
        }}>
          Ask a few things and this page fills in. It\u2019s where I keep what I\u2019ve picked up
          about how you like to be talked to — never which products I rank.
        </p>

        {/* Editorial CTA — feels like a magazine pull-quote, not a button */}
        <div style={{
          marginTop: 36,
          padding: '20px 22px',
          background: mc.paperHi,
          border: `1px solid ${mc.line}`,
          borderRadius: 14,
          display: 'flex', alignItems: 'center', gap: 14,
        }}>
          <div style={{
            width: 38, height: 38, borderRadius: 999,
            background: mc.ink,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flex: '0 0 38px',
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M5 12h14M13 6l6 6-6 6" stroke={mc.paper} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{
              fontFamily: mf.sans, fontSize: 14, fontWeight: 500, color: mc.ink,
            }}>Ask your first thing</div>
            <div style={{
              marginTop: 2, fontFamily: mf.sans, fontSize: 12, color: mc.ink2,
            }}>One real question is enough to start.</div>
          </div>
        </div>

        {/* Greyed-out preview of what fills in — sets expectations */}
        <div style={{ marginTop: 40 }}>
          <Eyebrow>What lives here, eventually</Eyebrow>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, opacity: .42 }}>
            {[
              'How you like to be talked to',
              'Your usual priorities',
              'Categories you\u2019ve explored',
            ].map((t, i) => (
              <div key={i} style={{
                padding: '12px 14px',
                background: mc.paperAlt,
                border: `1px dashed ${mc.line2}`,
                borderRadius: 10,
                fontFamily: mf.sans, fontSize: 13, color: mc.ink2,
              }}>{t}</div>
            ))}
          </div>
          <div style={{
            marginTop: 14,
            fontFamily: mf.sans, fontSize: 11, color: mc.ink3,
            letterSpacing: '0.04em',
          }}>Filled in by your conversations · never by a form.</div>
        </div>
      </div>

      <TabBar active="profile" />
    </Phone>
  );
}

// ============================================================
// 10b. PERSONALITY PROFILE — POPULATED (post-MVP reference)
// Kept from the locked first pass.
// ============================================================
function ProfileScreenFull() {
  return (
    <Phone label="About you" height={1320}>
      <Header
        title=""
        back
        right={
          <span style={{
            fontFamily: mf.sans, fontSize: 12, color: mc.ink2, fontWeight: 500,
          }}>Done</span>
        }
      />

      <div style={{ padding: '8px 26px 0' }}>
        <div className="rg-eyebrow" style={{ marginBottom: 10 }}>About you</div>
        <h1 style={{
          margin: 0, fontFamily: mf.display, fontStyle: 'italic',
          fontSize: 34, lineHeight: '38px', letterSpacing: '-0.02em',
          color: mc.ink, fontWeight: 400,
        }}>What I’ve picked up so far.</h1>
        <p style={{
          margin: '14px 0 0',
          fontFamily: mf.serif, fontSize: 16, lineHeight: '24px',
          color: mc.ink2, letterSpacing: '-0.005em',
        }}>
          A few things I’ve learned from the way we talk. Edit anything that’s off —
          it shapes how short or technical I get, never which products I rank.
        </p>
      </div>

      {/* Section 1 — How you like to be talked to */}
      <div style={{ padding: '28px 26px 0' }}>
        <Eyebrow action="Doesn’t sound like me">How you like to be talked to</Eyebrow>
        <p style={{
          margin: 0, fontFamily: mf.serif, fontSize: 17, lineHeight: '26px',
          color: mc.ink, letterSpacing: '-0.005em',
        }}>
          You’re comfortable with technical specs — I’ll keep it short. You push back when you don’t agree, so
          I’ll show my work when the call is close. You read the long blog when it’s a real decision and skim
          when it isn’t.
        </p>
      </div>

      {/* Section 2 — Your usual priorities */}
      <div style={{ padding: '28px 26px 0' }}>
        <Eyebrow action="Add">Your usual priorities</Eyebrow>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {[
            'Budget caps around $400',
            'Reliability over feature count',
            'Wireless over wired',
            'Glasses-friendly fit matters',
            'Skeptical of Sony software',
          ].map((p, i) => (
            <span key={i} style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              padding: '8px 6px 8px 12px',
              background: mc.paperHi, border: `1px solid ${mc.line}`,
              borderRadius: 999,
              fontFamily: mf.sans, fontSize: 13, color: mc.ink,
            }}>
              {p}
              <span style={{
                width: 18, height: 18, borderRadius: 999, background: mc.paperAlt,
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                color: mc.ink3,
              }}>
                <svg width="9" height="9" viewBox="0 0 12 12">
                  <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                </svg>
              </span>
            </span>
          ))}
        </div>
      </div>

      {/* Section 3 — Categories explored */}
      <div style={{ padding: '28px 26px 0' }}>
        <Eyebrow>Categories you’ve explored</Eyebrow>
        <p style={{
          margin: 0, fontFamily: mf.serif, fontSize: 15, lineHeight: '22px',
          color: mc.ink2,
        }}>
          Headphones, standing desks, running shoes, a pizza oven.
        </p>
      </div>

      {/* Reset */}
      <div style={{ padding: '36px 26px 36px' }}>
        <div className="rg-hairline" style={{ marginBottom: 18 }}/>
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div>
            <div style={{
              fontFamily: mf.sans, fontSize: 14, fontWeight: 500, color: mc.ink,
            }}>Reset what I’ve learned</div>
            <div style={{
              marginTop: 2, fontFamily: mf.sans, fontSize: 12, color: mc.ink3,
            }}>Keeps your chats and saves.</div>
          </div>
          <button style={{
            padding: '10px 14px', borderRadius: 999,
            background: 'transparent', border: `1px solid ${mc.line2}`,
            color: mc.danger, fontFamily: mf.sans, fontSize: 13, fontWeight: 500,
          }}>Reset</button>
        </div>
      </div>

      <TabBar active="profile" />
    </Phone>
  );
}

Object.assign(window, { LoadingScreen, SavedScreen, CompareScreen, ProfileScreen, ProfileScreenFull });
