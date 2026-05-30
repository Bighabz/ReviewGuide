// Results (the densest screen — editorial blog + carousel + sticky composer)
// and Product Detail.

const { color: rc, font: rf, radius: rr, shadow: rs } = window.RG;

// ============================================================
// 05. RESULTS — blog + carousel + sticky composer
// ============================================================
function ResultsScreen() {
  return (
    <Phone label="Results" height={2900}>
      <HeaderBrand
        back
        context="Wireless headphones · 4 sources"
        right={
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M4 7h16M7 12h10M10 17h4" stroke={rc.ink2} strokeWidth="1.4" strokeLinecap="round"/>
          </svg>
        }
      />

      {/* Prior conversation thread (scrolls up; partially visible).
          Per tone.md update: budget is the default first question on
          non-trivial purchases, so the AI asks before recommending. */}
      <div style={{ padding: '4px 22px 0', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <UserBubble>
          Best wireless headphones for daily commute, mostly trains. Glasses-wearer, lots of calls.
        </UserBubble>

        <AIBubble style={{ maxWidth: 320 }}>
          <p style={{ margin: 0, marginBottom: 12 }}>
            Happy to narrow this. Before I do — what&rsquo;s the rough budget?
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Chip leadingDot>Under $250</Chip>
            <Chip leadingDot>$250 – $400</Chip>
            <Chip leadingDot accent>Around $400, could stretch</Chip>
            <Chip leadingDot>No firm ceiling</Chip>
          </div>
        </AIBubble>

        <UserBubble>Around $400. Could stretch a bit if it&rsquo;s clearly worth it.</UserBubble>

        {/* Transitional reasoning — the inference the budget answer triggers */}
        <TransitionalBubble>
          $400 puts the better-call-quality tier on the table — that changes the pick for someone on calls all day.
        </TransitionalBubble>
      </div>

      {/* Long-form blog response */}
      <div style={{
        padding: '24px 24px 0',
        background: rc.paperHi,
        border: `1px solid ${rc.line}`,
        borderRadius: '18px 18px 18px 6px',
        margin: '16px 22px 0',
      }}>
        {/* Eyebrow */}
        <div style={{
          fontFamily: rf.sans, fontSize: 10, fontWeight: 600,
          letterSpacing: '0.14em', textTransform: 'uppercase',
          color: rc.terra, marginBottom: 10,
        }}>The pick</div>

        {/* Verdict lede */}
        <h2 style={{
          margin: 0, fontFamily: rf.display, fontStyle: 'italic',
          fontSize: 30, lineHeight: '36px', letterSpacing: '-0.015em',
          color: rc.ink, fontWeight: 400,
        }}>
          For glasses, calls, and the train every day —{' '}
          <span style={{ color: rc.ink, fontStyle: 'italic' }}>
            the <ProductLink>Bose QuietComfort Ultra</ProductLink>.
          </span>
        </h2>

        <div className="rg-hairline" style={{ margin: '22px -24px 22px' }}/>

        {/* Body — Newsreader serif at 16/26 */}
        <BlogBody>
          <p>
            The <ProductLink>QC Ultra</ProductLink> wins this for one reason most rankings underweight: <em>they sit
            kindly on glasses</em>. The earcup padding is softer than the <ProductLink>Sony XM5</ProductLink>’s, the
            clamp is gentler, and the temples don’t lift the seal the way they do on every Sony since the XM3.
            On a packed train, that’s the difference between forty minutes of music and forty minutes of
            re-adjusting.
          </p>
          <p>
            They also handle phone calls measurably better than the XM5 — which has been Sony’s known weak
            spot for three generations and shows no sign of changing.
          </p>
        </BlogBody>

        {/* Section break */}
        <BlogHead>If you want the Sony instead</BlogHead>
        <BlogBody>
          <p>
            The <ProductLink>XM5</ProductLink> is still the pick if you weight pure sound and codec support and
            you’re not on calls all day. Out-of-the-box tuning is warmer, the app is genuinely more flexible,
            and the case is slightly slimmer in a personal-item bag.
          </p>
          <p>
            Not the pick for your situation — but a real choice for someone whose commute is quieter and whose
            phone is on do-not-disturb.
          </p>
        </BlogBody>

        <BlogHead>The budget pick that’s genuinely good</BlogHead>
        <BlogBody>
          <p>
            If $429 feels steep, <ProductLink>Sonos Ace</ProductLink> at $349 gets you 85% of the QC Ultra
            experience with a case that’s actually thought through. Call quality is a half-step behind. Sound is
            a full step ahead of every other sub-$400 contender.
          </p>
        </BlogBody>

        <div className="rg-hairline" style={{ margin: '22px -24px 22px' }}/>

        {/* Curious follow-up — own line, italic display, terracotta hairline above */}
        <FollowUpQ>
          Want me to factor in glasses fit harder, or are you contact-lens-only when you’re wearing these?
        </FollowUpQ>
      </div>

      {/* Carousel — peek of next card on right edge */}
      <div style={{ marginTop: 24 }}>
        <div style={{ padding: '0 22px 8px' }}>
          <Eyebrow>The shortlist · 4 picks</Eyebrow>
        </div>
        <div style={{
          display: 'flex', gap: 12, overflowX: 'auto',
          padding: '0 22px 4px',
        }}>
          <ProductCard
            role="Top pick · for you"
            name="Bose QuietComfort Ultra"
            brand="Bose"
            price="$429"
            tint="#C5B7A2"
            img="#C5B7A2"
            saved
          />
          <ProductCard
            role="If you want Sony"
            roleAccent={false}
            name="Sony WH-1000XM5"
            brand="Sony"
            price="$399"
            tint="#B7BFC5"
            img="#B7BFC5"
          />
          <ProductCard
            role="Budget pick"
            roleAccent={false}
            name="Sonos Ace"
            brand="Sonos"
            price="$349"
            tint="#CFC8B8"
            img="#CFC8B8"
          />
          <ProductCard
            role="Lightweight alt"
            roleAccent={false}
            name="Sennheiser Momentum 4"
            brand="Sennheiser"
            price="$379"
            tint="#A8B0A8"
            img="#A8B0A8"
          />
        </div>
      </div>

      {/* Buffer so sticky composer can clear */}
      <div style={{ height: 130 }} />

      {/* Sticky composer — anchored to viewport bottom */}
      <Composer placeholder="Push back, narrow down, ask follow-up…"/>
    </Phone>
  );
}

// ----- Blog body helpers (encapsulates editorial type) -----
function BlogBody({ children }) {
  return (
    <div style={{
      fontFamily: rf.serif, fontSize: 16, lineHeight: '26px', color: rc.ink,
      letterSpacing: '-0.005em',
    }}>
      {React.Children.map(children, (ch, i) =>
        React.cloneElement(ch, {
          style: { ...(ch.props.style || {}), margin: 0, marginBottom: 14 }
        })
      )}
    </div>
  );
}
function BlogHead({ children }) {
  return (
    <h3 style={{
      margin: '6px 0 10px',
      fontFamily: rf.serif, fontSize: 18, lineHeight: '24px',
      letterSpacing: '-0.01em', color: rc.ink, fontWeight: 600,
    }}>{children}</h3>
  );
}


// ============================================================
// 06. PRODUCT DETAIL
// ============================================================
function ProductDetailScreen() {
  return (
    <Phone label="Product detail" height={1380}>
      <HeaderBrand
        back
        right={
          <div style={{
            width: 36, height: 36, borderRadius: 999, background: rc.paperAlt,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Bookmark filled size={18} />
          </div>
        }
      />

      {/* Hero image */}
      <div style={{
        height: 320, margin: '0 22px',
        background: '#C5B7A2', borderRadius: 18, position: 'relative', overflow: 'hidden',
      }}>
        <PlaceholderProduct tint="#C5B7A2" />
        {/* image dots */}
        <div style={{
          position: 'absolute', bottom: 14, left: 0, right: 0,
          display: 'flex', justifyContent: 'center', gap: 5,
        }}>
          {[0,1,2,3].map(i => (
            <span key={i} style={{
              width: 5, height: 5, borderRadius: 999,
              background: i === 0 ? rc.ink : 'rgba(26,24,22,.25)',
            }}/>
          ))}
        </div>
      </div>

      <div style={{ padding: '20px 24px 0' }}>
        {/* Role label */}
        <div style={{
          fontFamily: rf.sans, fontSize: 10, fontWeight: 600,
          letterSpacing: '0.14em', textTransform: 'uppercase',
          color: rc.terra, marginBottom: 8,
        }}>Top pick · best all-rounder for your situation</div>

        {/* Name */}
        <h1 style={{
          margin: 0, fontFamily: rf.serif, fontSize: 26, lineHeight: '32px',
          fontWeight: 600, letterSpacing: '-0.01em', color: rc.ink,
        }}>Bose QuietComfort Ultra</h1>
        <div style={{
          marginTop: 4, fontFamily: rf.sans, fontSize: 13, color: rc.ink2,
        }}>Bose · Over-ear · Wireless</div>

        {/* Price row */}
        <div style={{
          marginTop: 18,
          display: 'flex', alignItems: 'center', gap: 12, justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ fontFamily: rf.serif, fontSize: 24, color: rc.ink, fontWeight: 600 }}>$429</div>
            <div style={{ fontFamily: rf.sans, fontSize: 11, color: rc.ink3, marginTop: 2 }}>at Amazon</div>
          </div>
          <button style={{
            padding: '14px 22px', borderRadius: 999, border: 'none',
            background: rc.ink, color: rc.paper,
            fontFamily: rf.sans, fontSize: 14, fontWeight: 500,
            display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
          }}>
            Buy at Amazon
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M7 17 17 7M9 7h8v8" stroke={rc.paper} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>

        <div className="rg-hairline" style={{ margin: '24px 0' }}/>

        {/* AI take */}
        <div style={{
          fontFamily: rf.sans, fontSize: 10, fontWeight: 600,
          letterSpacing: '0.14em', textTransform: 'uppercase',
          color: rc.ink2, marginBottom: 10,
        }}>Why it’s your pick</div>
        <div style={{
          fontFamily: rf.serif, fontSize: 16, lineHeight: '26px', color: rc.ink,
        }}>
          The QC Ultra is the one in the carousel that takes glasses seriously. Soft earpads, a gentler clamp, and
          a seal that doesn’t lift around the temples — which matters more on a daily commute than people give
          it credit for. Calls are measurably clearer than the XM5. Battery is fine, not class-leading. Case is
          fine, not the worst.
        </div>

        <div className="rg-hairline" style={{ margin: '24px 0' }}/>

        {/* Specs — prose lines, not a table */}
        <div style={{
          fontFamily: rf.sans, fontSize: 10, fontWeight: 600,
          letterSpacing: '0.14em', textTransform: 'uppercase',
          color: rc.ink2, marginBottom: 10,
        }}>What matters here</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[
            ['ANC',         'Class-leading for cabin & train drone. Audible difference vs. XM5.'],
            ['Calls',       'Best-in-class mic array. Holds up on a windy platform.'],
            ['Comfort',     'Softest pads in the shortlist. Gentle on temple arms.'],
            ['Battery',     '24 hours w/ ANC. Mid-pack.'],
            ['Codec',       'aptX Adaptive. No LDAC (less of an issue than Reddit thinks).'],
          ].map(([k, v], i) => (
            <div key={i} style={{ display: 'flex', gap: 12 }}>
              <div style={{
                width: 64, flex: '0 0 64px',
                fontFamily: rf.sans, fontSize: 12, fontWeight: 600, color: rc.ink2,
                paddingTop: 1,
              }}>{k}</div>
              <div style={{
                fontFamily: rf.serif, fontSize: 15, lineHeight: '22px', color: rc.ink, flex: 1,
              }}>{v}</div>
            </div>
          ))}
        </div>

        <div className="rg-hairline" style={{ margin: '24px 0' }}/>

        {/* Pros & cons — voice consistent */}
        <div style={{
          fontFamily: rf.sans, fontSize: 10, fontWeight: 600,
          letterSpacing: '0.14em', textTransform: 'uppercase',
          color: rc.ink2, marginBottom: 10,
        }}>Honest notes</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {[
            ['+', 'Excellent for plane and train drone.'],
            ['+', 'Glasses-friendly clamp.'],
            ['+', 'Calls are the actual best in the shortlist.'],
            ['—', 'Case is bulkier than the XM5’s. Matters if your bag is tight.'],
            ['—', 'Bose app is competent but joyless. You won’t love EQ-ing in it.'],
          ].map(([sign, txt], i) => (
            <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <span style={{
                width: 14, fontFamily: rf.serif, fontStyle: 'italic',
                fontSize: 16, color: sign === '+' ? rc.terra : rc.ink2,
                lineHeight: '22px',
              }}>{sign}</span>
              <span style={{
                flex: 1, fontFamily: rf.serif, fontSize: 15, lineHeight: '22px', color: rc.ink,
              }}>{txt}</span>
            </div>
          ))}
        </div>
      </div>
    </Phone>
  );
}

Object.assign(window, { ResultsScreen, ProductDetailScreen, BlogBody, BlogHead });
