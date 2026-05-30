// v2 delta artboards — logo system, rotation spec, transitional reasoning bubble,
// updated quiz screen with reasoning bubble in context.

const { color: vc, font: vf } = window.RG;

// ============================================================
// V2 OPENING NOTE
// ============================================================
function V2OpeningCard() {
  return (
    <Card width={1240} height={null} style={{ background: vc.paperHi }}>
      <div className="rg-eyebrow" style={{ marginBottom: 14, color: vc.terra }}>v2 delta · logo + Discover + new components</div>
      <h1 style={{
        margin: 0, fontFamily: vf.display, fontStyle: 'italic',
        fontSize: 56, lineHeight: '60px', letterSpacing: '-0.025em',
        color: vc.ink, fontWeight: 400, maxWidth: 960,
      }}>The logo earns one bubble. After that, the product is editorial.</h1>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 40, marginTop: 28 }}>
        <p style={{
          margin: 0,
          fontFamily: vf.serif, fontSize: 16, lineHeight: '26px', color: vc.ink,
          letterSpacing: '-0.005em',
        }}>
          Five deltas on the locked v1 system. <em>One:</em> the existing
          ReviewGuide.Ai wordmark, rebuilt in terracotta on cream. <em>Two:</em> a
          single hero treatment with the speech-bubble and a rotating tagline word,
          used only on Discover. <em>Three:</em> a small static wordmark for every
          other page&rsquo;s header. <em>Four:</em> a quiz-path &ldquo;transitional reasoning&rdquo;
          bubble — the new component the tone update calls for. <em>Five:</em> the
          About-you screen reverts to its MVP empty state.
        </p>
        <p style={{
          margin: 0,
          fontFamily: vf.serif, fontSize: 16, lineHeight: '26px', color: vc.ink2,
          letterSpacing: '-0.005em',
        }}>
          Nothing else in the locked system moves. The decisions log from v1
          stays. The color, type, and component library stay. The Results blog
          stays. This brief is additive; below are only the surfaces that
          changed.
        </p>
      </div>
    </Card>
  );
}

// ============================================================
// LOGO SYSTEM — full bubble + static wordmark side-by-side
// ============================================================
function LogoSystemCard() {
  return (
    <Card eyebrow="Spec §11.7 · Logo & wordmark" title="Two treatments. One wordmark." width={1240} height={null}>
      <p style={{
        margin: '0 0 28px', maxWidth: 820,
        fontFamily: vf.serif, fontSize: 16, lineHeight: '26px',
        color: vc.ink2, letterSpacing: '-0.005em',
      }}>
        The wordmark is sans (DM Sans, 700 / 500 / 700 across &ldquo;Review&rdquo; /
        &ldquo;Guide&rdquo; / &ldquo;.Ai&rdquo;). Terracotta carries the brand syllables; ink carries the noun.
        The speech bubble exists in exactly one place: the Discover hero. Every
        other surface uses the bare wordmark, top-left, with a static lockup.
      </p>

      <div style={{
        display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 32,
        alignItems: 'stretch',
      }}>
        {/* HERO TREATMENT */}
        <div style={{
          padding: 36,
          background: vc.paper, borderRadius: 14,
          border: `1px solid ${vc.line}`,
          display: 'flex', flexDirection: 'column', alignItems: 'center',
        }}>
          <div className="rg-eyebrow" style={{ alignSelf: 'flex-start', marginBottom: 18, color: vc.terra }}>
            Treatment A · Discover hero
          </div>
          <LogoHero rotate width={360} />
          <div style={{
            marginTop: 28, fontFamily: vf.sans, fontSize: 12, lineHeight: '18px',
            color: vc.ink2, textAlign: 'center', maxWidth: 360,
          }}>
            One occurrence in the product. Tagline word rotates every 2.4s.
            Crossfade only — no slide, no scale. Bubble stroke is 2.5px terracotta.
          </div>
        </div>

        {/* STATIC TREATMENT */}
        <div style={{
          padding: 36,
          background: vc.paper, borderRadius: 14,
          border: `1px solid ${vc.line}`,
          display: 'flex', flexDirection: 'column',
        }}>
          <div className="rg-eyebrow" style={{ marginBottom: 18 }}>Treatment B · everywhere else</div>

          {/* Three sizes */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24, marginBottom: 24 }}>
            <div>
              <WordmarkStatic size={22} />
              <div style={{ marginTop: 8, fontFamily: vf.mono, fontSize: 10, color: vc.ink3 }}>22 / app header</div>
            </div>
            <div className="rg-hairline" />
            <div>
              <WordmarkStatic size={18} />
              <div style={{ marginTop: 8, fontFamily: vf.mono, fontSize: 10, color: vc.ink3 }}>18 / in-page header</div>
            </div>
            <div className="rg-hairline" />
            <div>
              <WordmarkStatic size={14} showTagline={false} />
              <div style={{ marginTop: 8, fontFamily: vf.mono, fontSize: 10, color: vc.ink3 }}>14 / footers, dense bars</div>
            </div>
          </div>

          <div style={{
            marginTop: 'auto', paddingTop: 16, borderTop: `1px solid ${vc.line}`,
            fontFamily: vf.sans, fontSize: 12, lineHeight: '18px', color: vc.ink2,
          }}>
            No bubble. Tagline is static (&ldquo;Ask before you buy&rdquo;) in 9pt small-caps below the
            wordmark, ink-3 muted. At the smallest size, the tagline drops away
            entirely — the wordmark holds the brand on its own.
          </div>
        </div>
      </div>

      <div className="rg-hairline" style={{ margin: '32px 0' }}/>

      {/* Wordmark anatomy */}
      <div className="rg-eyebrow" style={{ marginBottom: 18 }}>Wordmark anatomy</div>
      <div style={{
        padding: 32,
        background: vc.paperAlt, borderRadius: 12,
        display: 'flex', alignItems: 'center', gap: 48, flexWrap: 'wrap',
      }}>
        <Wordmark size={56} />
        <div style={{
          display: 'flex', flexDirection: 'column', gap: 8,
          fontFamily: vf.mono, fontSize: 11, color: vc.ink2,
        }}>
          <div><span style={{ color: vc.terra, fontWeight: 600 }}>Review</span> &nbsp;·&nbsp; DM Sans 700 · #B8543A</div>
          <div><span style={{ color: vc.ink, fontWeight: 500 }}>Guide</span> &nbsp;&nbsp;·&nbsp; DM Sans 500 · #1A1816</div>
          <div><span style={{ color: vc.terra, fontWeight: 600 }}>.Ai</span> &nbsp;&nbsp;&nbsp;&nbsp;·&nbsp; DM Sans 700 · #B8543A</div>
          <div>letter-spacing &nbsp;·&nbsp; -0.025em</div>
          <div>baseline &nbsp;&nbsp;&nbsp;·&nbsp; all three pieces aligned</div>
        </div>
      </div>
    </Card>
  );
}

// ============================================================
// ROTATION SPEC
// ============================================================
function RotationSpecCard() {
  const words = ['Buy', 'Eat', 'Fly', 'Stay', 'Book', 'Subscribe'];
  return (
    <Card eyebrow="Tagline rotation · spec for build" title="The rotating word." width={1240} height={null}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: 40 }}>

        {/* Spec table */}
        <div>
          <div className="rg-eyebrow" style={{ marginBottom: 14 }}>Behavior</div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {[
              ['Words',        'Buy → Eat → Fly → Stay → Book → Subscribe → (loop)'],
              ['Cycle',        '2.4s per word · 14.4s for a full loop'],
              ['Transition',   'Opacity crossfade only. 4px translateY-in, 4px translateY-out.'],
              ['Easing',       'ease-in-out · 14% in · 72% hold · 14% out'],
              ['Pause rule',   'Respects prefers-reduced-motion — falls back to static word "Buy".'],
              ['Width',        'Word slot reserves the width of the longest word ("Subscribe") so the line never reflows.'],
              ['Color',        '#B8543A · Instrument Serif Italic · sized 1.4× the surrounding sans line height.'],
              ['Off Discover', 'Tagline is static "Ask before you buy" — no rotation, no italic emphasis on the verb.'],
            ].map((r, i) => (
              <div key={i} style={{
                padding: '12px 0',
                borderBottom: `1px solid ${vc.line}`,
                display: 'grid', gridTemplateColumns: '120px 1fr', gap: 16,
              }}>
                <div style={{
                  fontFamily: vf.sans, fontSize: 11, fontWeight: 600, color: vc.ink2,
                  letterSpacing: '0.04em', textTransform: 'uppercase',
                }}>{r[0]}</div>
                <div style={{
                  fontFamily: vf.serif, fontSize: 14, lineHeight: '22px',
                  color: vc.ink, letterSpacing: '-0.005em',
                }}>{r[1]}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Visual cycle */}
        <div>
          <div className="rg-eyebrow" style={{ marginBottom: 14 }}>The cycle, frame by frame</div>
          <div style={{
            padding: 28,
            background: vc.paper, borderRadius: 14,
            border: `1px solid ${vc.line}`,
            display: 'flex', flexDirection: 'column', gap: 14,
          }}>
            {words.map((w, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'baseline', gap: 14,
                paddingBottom: 12,
                borderBottom: i < words.length - 1 ? `1px solid ${vc.line}` : 'none',
              }}>
                <span style={{
                  fontFamily: vf.mono, fontSize: 10, color: vc.ink3,
                  width: 48, letterSpacing: '0.04em',
                }}>{(i * 2.4).toFixed(1)}s</span>
                <span style={{
                  fontFamily: vf.sans, fontSize: 18, fontWeight: 500, color: vc.ink2,
                  letterSpacing: '-0.005em',
                }}>Ask Before You</span>
                <span style={{
                  fontFamily: vf.display, fontStyle: 'italic',
                  fontSize: 26, lineHeight: 1, color: vc.terra,
                  letterSpacing: '-0.01em',
                }}>{w}</span>
              </div>
            ))}
          </div>

          <div style={{
            marginTop: 18,
            padding: 14,
            background: vc.terraSoft,
            borderRadius: 10,
            border: `1px solid ${vc.terra}33`,
            fontFamily: vf.sans, fontSize: 12, lineHeight: '18px', color: vc.terraInk,
          }}>
            <strong style={{ fontWeight: 600 }}>Implementation note:</strong> use CSS animation
            (not setInterval) so iOS Safari low-power mode pauses it correctly. Single
            <code style={{ fontFamily: vf.mono, fontSize: 11 }}> @keyframes</code> with
            <code style={{ fontFamily: vf.mono, fontSize: 11 }}> animation-duration: 2.4s</code> and
            <code style={{ fontFamily: vf.mono, fontSize: 11 }}> animation-iteration-count: 1</code>;
            advance the word in JS at <code style={{ fontFamily: vf.mono, fontSize: 11 }}>animationiteration</code> /
            <code style={{ fontFamily: vf.mono, fontSize: 11 }}>animationend</code>, restart the animation.
          </div>
        </div>
      </div>
    </Card>
  );
}

// ============================================================
// TRANSITIONAL REASONING BUBBLE
// ============================================================
function TransitionalBubbleCard() {
  return (
    <Card eyebrow="New component · tone.md update" title="The transitional reasoning bubble." width={1240} height={null}>
      <p style={{
        margin: '0 0 28px', maxWidth: 820,
        fontFamily: vf.serif, fontSize: 16, lineHeight: '26px',
        color: vc.ink2, letterSpacing: '-0.005em',
      }}>
        Between two questions in the quiz path, when a user&rsquo;s answer triggers a real
        inference, the AI surfaces the reasoning <em>briefly</em> before asking the next one.
        This is the &ldquo;whoa, it gets me&rdquo; moment. The component reads as an aside, not a
        response — narrow, lighter-weight, no bubble background. Terracotta hairline
        on the left edge marks it as the AI thinking out loud.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 32 }}>

        {/* In-context demo */}
        <div style={{
          padding: 24,
          background: vc.paper, borderRadius: 18,
          border: `1px solid ${vc.line}`,
        }}>
          <div className="rg-eyebrow" style={{ marginBottom: 16 }}>In context · quiz turn</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <AIBubble>
              Got it. <span style={{ color: vc.ink2 }}>1 of 3 ·</span> what&rsquo;s the rough budget?
            </AIBubble>
            <UserBubble>Around $400. I also wear glasses, if that matters.</UserBubble>

            {/* THE NEW COMPONENT */}
            <TransitionalBubble>
              Glasses changes the shortlist — the clamp matters more than the spec sheet on this one.
            </TransitionalBubble>

            <AIBubble>
              <span style={{ fontFamily: vf.sans }}>One more: how loud is your usual room?</span>
              <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <Chip leadingDot>Quiet — home office</Chip>
                <Chip leadingDot accent>Loud — train commute</Chip>
                <Chip leadingDot>Open-plan office</Chip>
              </div>
            </AIBubble>
          </div>
        </div>

        {/* Anatomy */}
        <div>
          <div className="rg-eyebrow" style={{ marginBottom: 14 }}>Anatomy</div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {[
              ['Container',     'No bubble background. 1px terracotta hairline on left edge. 14px left padding.'],
              ['Type',          'Instrument Serif Italic, 17/24, ink. Same family as the curious follow-up Q.'],
              ['Max width',     '~280px. Narrower than the AI bubble so it reads as inset.'],
              ['Indent',        '8px from the chat gutter so it doesn\u2019t hard-align with normal bubbles.'],
              ['When to use',   'Between user reply and next AI question, when the user\u2019s answer changed the shortlist meaningfully. Never on routine confirmations ("got it") — that\u2019s noise.'],
              ['Voice',         'Compressed-consensus shorthand from tone.md §Synthesized authority — "what matters", "the tradeoff", "the catch". Always one sentence.'],
              ['Animation',     'Fade-in over 200ms after the user bubble lands. The next AI question follows 600ms after the reasoning bubble settles.'],
            ].map((r, i) => (
              <div key={i} style={{
                padding: '12px 0',
                borderBottom: i < 6 ? `1px solid ${vc.line}` : 'none',
                display: 'grid', gridTemplateColumns: '110px 1fr', gap: 14,
              }}>
                <div style={{
                  fontFamily: vf.sans, fontSize: 10, fontWeight: 600, color: vc.ink2,
                  letterSpacing: '0.08em', textTransform: 'uppercase',
                }}>{r[0]}</div>
                <div style={{
                  fontFamily: vf.serif, fontSize: 13, lineHeight: '20px',
                  color: vc.ink, letterSpacing: '-0.005em',
                }}>{r[1]}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rg-hairline" style={{ margin: '32px 0 22px' }}/>

      {/* More examples */}
      <div className="rg-eyebrow" style={{ marginBottom: 18 }}>More examples — voice register</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24 }}>
        <div>
          <TransitionalBubble>
            That budget actually opens up the better-call-quality tier — worth knowing.
          </TransitionalBubble>
          <div style={{ marginTop: 10, fontFamily: vf.mono, fontSize: 10, color: vc.ink3 }}>after: budget answer</div>
        </div>
        <div>
          <TransitionalBubble>
            Daily commute makes ANC the through-line. Sound character matters less than I&rsquo;d ordinarily say.
          </TransitionalBubble>
          <div style={{ marginTop: 10, fontFamily: vf.mono, fontSize: 10, color: vc.ink3 }}>after: use-case answer</div>
        </div>
        <div>
          <TransitionalBubble>
            Sony software being a deal-breaker narrows this to two real picks.
          </TransitionalBubble>
          <div style={{ marginTop: 10, fontFamily: vf.mono, fontSize: 10, color: vc.ink3 }}>after: brand preference</div>
        </div>
      </div>
    </Card>
  );
}

// ============================================================
// V2 QUIZ SCREEN — full screen with the transitional reasoning bubble in flow
// ============================================================
function ChatQuizV2Screen() {
  return (
    <Phone label="Chat — quiz path v2" height={1020}>
      <HeaderBrand back context="Wireless headphones" />

      <div style={{
        padding: '8px 22px 0', display: 'flex', flexDirection: 'column', gap: 14,
      }}>
        <UserBubble>I need new headphones for commute.</UserBubble>

        <AIBubble>
          Happy to narrow this. First — <span style={{ color: vc.ink2 }}>1 of 3 ·</span> what&rsquo;s the rough budget?
        </AIBubble>

        <UserBubble>Around $400. I also wear glasses.</UserBubble>

        {/* Transitional reasoning — the new beat */}
        <TransitionalBubble>
          Glasses changes the shortlist — the clamp matters more than the spec sheet on this one.
        </TransitionalBubble>

        <AIBubble style={{ maxWidth: 320 }}>
          <p style={{ margin: 0, marginBottom: 12 }}>
            <span style={{ color: vc.ink2 }}>2 of 3 ·</span> how loud is your usual room?
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Chip leadingDot>Quiet — home office</Chip>
            <Chip leadingDot accent>Loud — train commute</Chip>
            <Chip leadingDot>Open-plan office</Chip>
          </div>
        </AIBubble>
      </div>

      <Composer placeholder="Type a reply…" />
    </Phone>
  );
}

Object.assign(window, {
  V2OpeningCard, LogoSystemCard, RotationSpecCard,
  TransitionalBubbleCard, ChatQuizV2Screen,
});
