// Foundation cards: color identity (3 directions), type system, components, decisions, spec feedback.

const { color: fc, font: ff, radius: fr, shadow: fs } = window.RG;

// ---------- Helpers ----------
function Card({ title, eyebrow, children, width = 720, height, style = {} }) {
  return (
    <div className="rg-frame" style={{
      width, height, background: fc.paperHi,
      borderRadius: 18, border: `1px solid ${fc.line}`,
      padding: 28, fontFamily: ff.sans, color: fc.ink,
      ...style,
    }}>
      {eyebrow && <div className="rg-eyebrow" style={{ marginBottom: 8 }}>{eyebrow}</div>}
      {title && (
        <h2 style={{
          margin: 0, fontFamily: ff.display, fontStyle: 'italic',
          fontSize: 28, lineHeight: '32px', letterSpacing: '-0.02em',
          color: fc.ink, fontWeight: 400, marginBottom: 22,
        }}>{title}</h2>
      )}
      {children}
    </div>
  );
}

function Swatch({ hex, name, role, fg = '#1A1816', label = null, big = false }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 6, flex: '0 0 auto',
      width: big ? 168 : 120,
    }}>
      <div style={{
        height: big ? 96 : 64, background: hex,
        borderRadius: 8, border: `1px solid ${fc.line}`,
        display: 'flex', alignItems: 'flex-end', padding: '8px 10px',
        fontFamily: ff.mono, fontSize: 10, color: fg, letterSpacing: '0.04em',
      }}>{label}</div>
      <div>
        <div style={{ fontFamily: ff.sans, fontSize: 13, fontWeight: 500, color: fc.ink }}>{name}</div>
        <div style={{ fontFamily: ff.mono, fontSize: 11, color: fc.ink2 }}>{hex}</div>
        {role && <div style={{ fontFamily: ff.sans, fontSize: 11, color: fc.ink3, marginTop: 2 }}>{role}</div>}
      </div>
    </div>
  );
}

// ============================================================
// COLOR IDENTITY — direction A (default), plus B/C alts for §13 #10
// ============================================================
function ColorIdentityCard() {
  return (
    <Card eyebrow="§13 · 10  ·  Color identity" title="Three directions. Default: terracotta on cream." width={1240} height={720}>
      <p style={{
        margin: 0, marginBottom: 28,
        fontFamily: ff.serif, fontSize: 16, lineHeight: '26px',
        color: fc.ink2, maxWidth: 820, letterSpacing: '-0.005em',
      }}>
        The spec rules out AI purple/blue and saturated gradients. All three directions sit on warm cream
        (<span className="rg-mono">#FAFAF7</span>) with the same ink (<span className="rg-mono">#1A1816</span>) —
        the only thing that changes is the accent. Contrast checked at body sizes against cream.
      </p>

      <div style={{ display: 'flex', gap: 28, marginBottom: 28 }}>
        {/* Default — terracotta */}
        <div style={{ flex: 1 }}>
          <div style={{
            display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 12,
          }}>
            <span style={{
              fontFamily: ff.sans, fontSize: 10, fontWeight: 600,
              letterSpacing: '0.12em', textTransform: 'uppercase', color: fc.terra,
            }}>Default · Recommended</span>
          </div>
          <h3 style={{
            margin: '0 0 6px', fontFamily: ff.display, fontStyle: 'italic',
            fontSize: 22, lineHeight: '26px', color: fc.ink, fontWeight: 400,
          }}>Terracotta on cream</h3>
          <p style={{
            margin: '0 0 16px', fontFamily: ff.serif, fontSize: 14, lineHeight: '22px',
            color: fc.ink2, letterSpacing: '-0.005em',
          }}>
            Earthy, editorial, print-magazine. The accent reads as a printer’s ink — present in
            section labels and active states, never as a wash. The matching spec’s interim color.
          </p>
          <div style={{ display: 'flex', gap: 10 }}>
            <Swatch hex="#B8543A" name="Terracotta"  role="Accent · 4.8:1" fg="#fff" label="B8543A"/>
            <Swatch hex="#F4E2D7" name="Soft"        role="Tint · save fill" label="F4E2D7"/>
            <Swatch hex="#7A3624" name="Ink"         role="Hover / pressed" fg="#fff" label="7A3624"/>
          </div>
        </div>

        {/* Alt B — mustard */}
        <div style={{ flex: 1, opacity: .7 }}>
          <div style={{
            display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 12,
          }}>
            <span style={{
              fontFamily: ff.sans, fontSize: 10, fontWeight: 600,
              letterSpacing: '0.12em', textTransform: 'uppercase', color: fc.ink2,
            }}>Alt B</span>
          </div>
          <h3 style={{
            margin: '0 0 6px', fontFamily: ff.display, fontStyle: 'italic',
            fontSize: 22, lineHeight: '26px', color: fc.ink, fontWeight: 400,
          }}>Ink + Mustard</h3>
          <p style={{
            margin: '0 0 16px', fontFamily: ff.serif, fontSize: 14, lineHeight: '22px',
            color: fc.ink2, letterSpacing: '-0.005em',
          }}>
            More austere — Monocle-magazine register. Mustard reads quieter than terracotta;
            the AI feels more like a researcher, less like a critic.
          </p>
          <div style={{ display: 'flex', gap: 10 }}>
            <Swatch hex="#C08A2E" name="Mustard"  role="Accent · 4.0:1" fg="#1A1816" label="C08A2E"/>
            <Swatch hex="#F1E4C6" name="Soft"     role="Tint" label="F1E4C6"/>
            <Swatch hex="#7E5A1A" name="Ink"      role="Hover" fg="#fff" label="7E5A1A"/>
          </div>
        </div>

        {/* Alt C — forest */}
        <div style={{ flex: 1, opacity: .7 }}>
          <div style={{
            display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 12,
          }}>
            <span style={{
              fontFamily: ff.sans, fontSize: 10, fontWeight: 600,
              letterSpacing: '0.12em', textTransform: 'uppercase', color: fc.ink2,
            }}>Alt C</span>
          </div>
          <h3 style={{
            margin: '0 0 6px', fontFamily: ff.display, fontStyle: 'italic',
            fontSize: 22, lineHeight: '26px', color: fc.ink, fontWeight: 400,
          }}>Ink + Forest</h3>
          <p style={{
            margin: '0 0 16px', fontFamily: ff.serif, fontSize: 14, lineHeight: '22px',
            color: fc.ink2, letterSpacing: '-0.005em',
          }}>
            Outdoorsy, trust-leaning — REI-catalog energy. The right call if the product later
            leans into longevity / repairability stories. Reads slightly more corporate.
          </p>
          <div style={{ display: 'flex', gap: 10 }}>
            <Swatch hex="#2B5337" name="Forest" role="Accent · 8.6:1" fg="#fff" label="2B5337"/>
            <Swatch hex="#DDE6DC" name="Soft"   role="Tint" label="DDE6DC"/>
            <Swatch hex="#1B3924" name="Ink"    role="Hover" fg="#fff" label="1B3924"/>
          </div>
        </div>
      </div>

      <div className="rg-hairline" style={{ margin: '12px 0 22px' }}/>

      {/* Neutrals */}
      <div className="rg-eyebrow" style={{ marginBottom: 12 }}>Shared neutrals</div>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <Swatch hex="#FAFAF7" name="Paper"   role="Background" label="FAFAF7"/>
        <Swatch hex="#FFFFFF" name="Paper Hi" role="Bubble, sheet" label="FFFFFF"/>
        <Swatch hex="#F5F4F0" name="Paper Alt" role="Sunken" label="F5F4F0"/>
        <Swatch hex="#E8E6E1" name="Line"    role="Hairlines" label="E8E6E1"/>
        <Swatch hex="#9B9590" name="Ink 3" role="Tertiary · 4.6:1" fg="#fff" label="9B9590"/>
        <Swatch hex="#6B6560" name="Ink 2" role="Secondary · 6.9:1" fg="#fff" label="6B6560"/>
        <Swatch hex="#1A1816" name="Ink"   role="Primary · 16.4:1" fg="#fff" label="1A1816"/>
      </div>
    </Card>
  );
}

// ============================================================
// TYPE SYSTEM
// ============================================================
function TypeCard() {
  return (
    <Card eyebrow="§13 · 5  ·  Blog typographic system" title="Three faces. Each does one job." width={1240} height={780}>
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 40 }}>
        <div>
          <div style={{
            fontFamily: ff.display, fontStyle: 'italic', fontSize: 96, lineHeight: '92px',
            letterSpacing: '-0.03em', color: fc.ink, marginBottom: -4,
          }}>Aa</div>
          <div style={{ fontFamily: ff.sans, fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Instrument Serif</div>
          <div style={{ fontFamily: ff.sans, fontSize: 12, color: fc.ink2, lineHeight: '18px' }}>
            Display only — hero greetings, verdict lede, the curious follow-up question, blog section heads.
            Italic does most of the work. Never below 18pt.
          </div>
        </div>
        <div>
          <div style={{
            fontFamily: ff.display, fontStyle: 'italic', fontSize: 44, lineHeight: '48px',
            letterSpacing: '-0.02em', color: fc.ink, marginBottom: 14,
          }}>What are you researching?</div>
          <div style={{
            fontFamily: ff.display, fontStyle: 'italic', fontSize: 22, lineHeight: '28px',
            color: fc.ink2, letterSpacing: '-0.005em',
          }}>Want me to factor in glasses fit, or are you contact-lens-only?</div>
        </div>
      </div>

      <div className="rg-hairline" style={{ margin: '28px 0' }}/>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 40 }}>
        <div>
          <div style={{
            fontFamily: ff.serif, fontSize: 96, lineHeight: '96px',
            letterSpacing: '-0.02em', color: fc.ink, marginBottom: -4, fontWeight: 500,
          }}>Aa</div>
          <div style={{ fontFamily: ff.sans, fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Newsreader</div>
          <div style={{ fontFamily: ff.sans, fontSize: 12, color: fc.ink2, lineHeight: '18px' }}>
            Blog body — 16/26. Designed for sustained reading. Used everywhere the AI is writing
            longer than one sentence. Italic for emphasis only.
          </div>
        </div>
        <div>
          <p style={{
            margin: 0, fontFamily: ff.serif, fontSize: 16, lineHeight: '26px', color: fc.ink,
            letterSpacing: '-0.005em', maxWidth: 620,
          }}>
            The QC Ultra wins this for one reason most rankings underweight: <em>they sit kindly on
            glasses</em>. The clamp is gentler, the earcup padding is softer than the XM5’s, and the temples
            don’t lift the seal.
          </p>
        </div>
      </div>

      <div className="rg-hairline" style={{ margin: '28px 0' }}/>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 40 }}>
        <div>
          <div style={{
            fontFamily: ff.sans, fontSize: 96, lineHeight: '96px', fontWeight: 500,
            letterSpacing: '-0.02em', color: fc.ink, marginBottom: -4,
          }}>Aa</div>
          <div style={{ fontFamily: ff.sans, fontSize: 14, fontWeight: 600, marginBottom: 4 }}>DM Sans</div>
          <div style={{ fontFamily: ff.sans, fontSize: 12, color: fc.ink2, lineHeight: '18px' }}>
            UI everywhere — chips, buttons, navigation, eyebrow labels, prices.
            Weights 400/500/600. Small-caps at 10/12px with 0.10–0.14em tracking for editorial section labels.
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, alignItems: 'flex-start' }}>
          <div style={{
            fontFamily: ff.sans, fontSize: 10, fontWeight: 600,
            letterSpacing: '0.14em', textTransform: 'uppercase', color: fc.terra,
          }}>Top pick · best all-rounder</div>
          <div style={{ fontFamily: ff.sans, fontSize: 14, fontWeight: 500 }}>Reply with anything</div>
          <Chip>Under $400</Chip>
          <div style={{ fontFamily: ff.sans, fontSize: 13, color: fc.ink2 }}>Saved on this device · 6 items</div>
        </div>
      </div>
    </Card>
  );
}

// ============================================================
// COMPONENT LIBRARY — spec §8
// ============================================================
function ComponentLibraryCard() {
  return (
    <Card eyebrow="Spec §8 · Component library" title="The pieces, once. Reused everywhere." width={1240} height={null}>

      {/* Bubbles */}
      <div className="rg-eyebrow" style={{ marginBottom: 14 }}>Chat bubbles · §8.1</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 24 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Annotation>AI bubble (short) — used in quiz turns &amp; follow-ups.</Annotation>
          <AIBubble>
            Got it. <span style={{ color: fc.ink2 }}>1 of 3 ·</span> what’s the rough budget?
          </AIBubble>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Annotation>User bubble — right-aligned, ink-on-cream inverted.</Annotation>
          <UserBubble>Best wireless earbuds under $100?</UserBubble>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Annotation kind="decision">Loading bubble — single breathing dot, rotating curious copy. §13 #1.</Annotation>
          <LoadingBubble />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Annotation kind="decision">Follow-up Q — Instrument Serif Italic, terracotta hairline above. §13 #3.</Annotation>
          <AIBubble>
            <span style={{ fontFamily: ff.serif, fontSize: 15, lineHeight: '22px' }}>
              Short blog body line just for context.
            </span>
            <FollowUpQ>
              Curious if budget is firm — there’s a $100 step-down worth considering.
            </FollowUpQ>
          </AIBubble>
        </div>
      </div>

      <div className="rg-hairline" style={{ margin: '28px 0' }}/>

      {/* Chips */}
      <div className="rg-eyebrow" style={{ marginBottom: 14 }}>Suggestion chip · §8.2 · §13 #4</div>
      <Annotation kind="decision" style={{ marginBottom: 12 }}>
        Rounded-rect (not capsule), left-aligned text, dot-led at quiz time, asymmetric so it reads as
        "tap to reply" — never as a multi-select form option.
      </Annotation>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 14 }}>
        <Chip leadingDot>Under $1,200</Chip>
        <Chip leadingDot accent>$1,200 – $1,800</Chip>
        <Chip leadingDot>$1,800 – $2,500</Chip>
        <Chip leadingDot>No firm ceiling</Chip>
      </div>

      <div className="rg-hairline" style={{ margin: '28px 0' }}/>

      {/* Inline product link */}
      <div className="rg-eyebrow" style={{ marginBottom: 14 }}>Inline product link · §8.5 · §13 #2</div>
      <Annotation kind="decision" style={{ marginBottom: 12 }}>
        Ink-colored text, dotted terracotta underline, 4px offset. Reads like editorial hyperlink, not button.
        Tap snaps the carousel to the matching card after scrolling carousel into view.
      </Annotation>
      <div style={{
        fontFamily: ff.serif, fontSize: 16, lineHeight: '26px', color: fc.ink, maxWidth: 560,
      }}>
        The <ProductLink>QC Ultra</ProductLink> wins this for one reason most rankings underweight — they
        sit kindly on glasses. The <ProductLink>Sony XM5</ProductLink> remains the pick when sound character
        outweighs call quality.
      </div>

      <div className="rg-hairline" style={{ margin: '28px 0' }}/>

      {/* Carousel card density */}
      <div className="rg-eyebrow" style={{ marginBottom: 14 }}>Carousel card · §8.4 · §13 #7</div>
      <Annotation kind="decision" style={{ marginBottom: 12 }}>
        240w × ~320h. Role label (10pt small-caps), name (Newsreader 17pt), brand, price, save.
        Image is the differentiator at a glance. ~50px peek of next card.
      </Annotation>
      <div style={{ display: 'flex', gap: 12, overflow: 'hidden' }}>
        <ProductCard role="Top pick · for you" name="Bose QuietComfort Ultra" brand="Bose" price="$429" tint="#C5B7A2" img="#C5B7A2" saved/>
        <ProductCard role="If you want Sony" roleAccent={false} name="Sony WH-1000XM5" brand="Sony" price="$399" tint="#B7BFC5" img="#B7BFC5"/>
        <ProductCard role="Budget pick" roleAccent={false} name="Sonos Ace" brand="Sonos" price="$349" tint="#CFC8B8" img="#CFC8B8"/>
        <ProductCard role="Lightweight alt" roleAccent={false} name="Sennheiser Momentum 4" brand="Sennheiser" price="$379" tint="#A8B0A8" img="#A8B0A8"/>
      </div>

      <div className="rg-hairline" style={{ margin: '28px 0' }}/>

      {/* Save toggle + Composer */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 28 }}>
        <div>
          <div className="rg-eyebrow" style={{ marginBottom: 14 }}>Save toggle · §8.7 · §13 #9</div>
          <Annotation kind="decision" style={{ marginBottom: 12 }}>
            Tap fills + 1px ring expands and fades (140ms). No toast. The icon flip <em>is</em> the confirmation.
          </Annotation>
          <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
            <Bookmark size={26}/>
            <Bookmark size={26} filled ring/>
            <Bookmark size={26} filled/>
          </div>
        </div>
        <div>
          <div className="rg-eyebrow" style={{ marginBottom: 14 }}>Sticky composer · §8.6</div>
          <Annotation style={{ marginBottom: 12 }}>
            Always anchored to viewport bottom. Soft cream gradient mask so the blog never butts hard into it.
          </Annotation>
          <div style={{ position: 'relative', height: 84 }}>
            <Composer placeholder="Reply with anything"/>
          </div>
        </div>
      </div>

    </Card>
  );
}

// ============================================================
// DECISIONS LOG — every §13 question, answered
// ============================================================
function DecisionsCard() {
  const rows = [
    ['1. Loading animation',
      'Single 8px terracotta dot, breathing 1.6s. Italic-display copy beside it, rotating every ~2s through the spec’s ambiguous vocabulary.',
      'Three-dot typing or spinner is the chatbot cliché the voice exists to dodge. One dot reads as "thinking", not "loading bar".'],
    ['2. Inline product hyperlink',
      'Ink-colored text + dotted terracotta underline, 4px offset. No background, no button chrome.',
      'Editorial precedent (NYT, The Atlantic). A button-style link breaks the "the editor is writing to you" feel.'],
    ['3. Curious follow-up Q',
      'Inside the AI bubble. 24px terracotta hairline above it, then Instrument Serif Italic 19/26 on its own line.',
      'Hairline marks a beat; italic-serif marks the AI leaning in. Stays inside the bubble so it doesn’t become a separate UI element.'],
    ['4. Suggestion chip',
      'Rounded-rect (12px), 1px paper-line border, leading 4px dot at quiz time, text left-aligned, variable width.',
      'Capsule pills + center-aligned text reads as "select-one form field". Left-aligned reads as "tap to reply".'],
    ['5. Blog typography',
      'Newsreader 16/26 body. Instrument Serif Italic display for lede + heads + follow-up Q. DM Sans for UI/eyebrow labels.',
      'Newsreader is designed for editorial reading at body sizes; Instrument Serif works as italic display but is too stylized at 16. Three faces, each does one job.'],
    ['6. Discover composition',
      'Vertical rhythm: greeting → prompt → trending chips (horizontal) → popular grid (vertical list with thumbnails) → recent chats. Section labels in 10pt small-caps.',
      'A grid-everywhere feed would feel algorithmic; an essay-shaped page reads as curated. Sections separated by air, not boxes.'],
    ['7. Carousel card density',
      '240w × ~320h. Image-top (75% width), role small-caps label, name in Newsreader 17, brand + price row, save in floating pill.',
      'Pure image carousels can\'t support a "for you" role label; pure text cards lose the product-shopping pleasure. Vertical card with role + name as the differentiators.'],
    ['8. Profile aesthetic',
      'Magazine "About the contributor" register. Display-italic title ("What I’ve picked up so far.") + Newsreader paragraph attributes + removable priority chips. Not a settings list.',
      'The spec said this does trust work. A settings page reads as plumbing; a written-out page reads as the AI showing its homework.'],
    ['9. Save toggle motion',
      'Bookmark fills terracotta; a 1px ring scales 0.6→1.6 and fades over 140ms. Icon scales 0.9→1.05→1.0 over 200ms. No toast.',
      'Spec is explicit: no toasts. Motion needs to land without being a notification.'],
    ['10. Color identity',
      'Default: terracotta #B8543A on cream #FAFAF7, ink #1A1816. Two alts shown above (mustard, forest).',
      'Terracotta is the spec’s interim color, contrast-passes at body sizes, and reads as printer-ink. Forest reads more "outdoor brand". Mustard reads quieter — best if the product later wants to dial confidence down.'],
  ];
  return (
    <Card eyebrow="§13 · Open questions" title="Calls I’m making. Reasoning attached." width={1240} height={null}>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {rows.map((r, i) => (
          <div key={i} style={{
            display: 'grid', gridTemplateColumns: '220px 1fr 1fr',
            gap: 24, padding: '18px 0',
            borderBottom: i < rows.length - 1 ? `1px solid ${fc.line}` : 'none',
          }}>
            <div style={{
              fontFamily: ff.display, fontStyle: 'italic',
              fontSize: 19, lineHeight: '24px',
              color: fc.ink, letterSpacing: '-0.005em',
            }}>{r[0]}</div>
            <div style={{
              fontFamily: ff.serif, fontSize: 14, lineHeight: '22px',
              color: fc.ink, letterSpacing: '-0.005em',
            }}>{r[1]}</div>
            <div style={{
              fontFamily: ff.sans, fontSize: 12, lineHeight: '18px',
              color: fc.ink2,
              paddingLeft: 16, borderLeft: `1px solid ${fc.line}`,
            }}>
              <span className="rg-eyebrow" style={{ display: 'block', marginBottom: 4 }}>Why</span>
              {r[2]}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ============================================================
// SPEC FEEDBACK — pushback for the build phase
// ============================================================
function SpecFeedbackCard() {
  const items = [
    ['Follow-up turns will pile editorial-length blogs into the thread.',
      'Spec §7.5 / §9.5: "the prior blog scrolls up into the conversation thread." A full blog can be 800–1,200px tall on mobile; after 3 turns the user has thousands of px to scroll past to see history.',
      'Collapse prior blogs to a 1-line "verdict lede" with the carousel still visible as a thin scroll-strip; tap to re-expand. Live blog is full; only previous ones collapse. Annotation included on the Results artboard.'],
    ['"Tap to edit" on derived attributes (§7.10) is ambiguous.',
      'For "How you like to be talked to" the AI infers a paragraph. What does the user actually edit — the prose, or underlying register/depth dimensions?',
      'Treat the paragraph as read-only; expose one "Doesn’t sound like me" link that opens a sheet with 2–3 register dimensions (formal↔casual, brief↔thorough). Removable priority chips stay separate (they are user-statable).'],
    ['Inline product link → carousel snap, when carousel is offscreen.',
      '§9.3 says tap snaps the carousel to that card. But on Results the carousel sits below a long blog; a "snap" with no scroll is invisible to the user.',
      'Two-step: smooth-scroll the carousel container into view first (anchored at viewport bottom above the composer), THEN snap to the target card. ~280ms total, single ease.'],
    ['Sticky composer + carousel peek-of-next collision.',
      'Composer is sticky to viewport bottom (§9.4). Carousel cards must clear it — otherwise the rightmost peek is permanently hidden under the composer’s soft gradient.',
      'Add 96px of post-carousel buffer in the document flow; the cream-to-transparent gradient on the composer fades over the buffer, not over the cards.'],
    ['"No skeleton loaders" + "loading bubble transforms into blog" is hand-wavy.',
      '§9.5 says smooth transition, not jarring swap. With a 1,200px blog this is a real layout-shift problem.',
      'Specified: the loading bubble fades out (200ms), then the blog renders top-down with section-staggered opacity (3 × 100ms steps). No height animation — the bubble simply gets replaced; the page below it grows. The composer stays put.'],
    ['Chat-empty starter prompt + chips + composer fight for vertical space.',
      'With keyboard up (~340px on iPhone 15), the visible area is ~470px. A starter prompt + 4 chips + composer is tight.',
      'When keyboard opens: starter prompt scales to 24/28 (from 30/34) and chips collapse to 3. When keyboard closes: full layout restores. Subtle, no animation needed.'],
    ['Trending chips on Discover have no category cue.',
      'Spec §7.1 lists chip topics with no metadata. Mixed-category demo ("headphones," "hotels," "laptops") reads as random without a tag.',
      'Added a 9pt small-caps category tag on each trending card (Audio, Travel, Tech, Kitchen, Fitness). One tag, no nesting. Mirrors the same eyebrow vocabulary used in the rest of the design.'],
    ['Compare flow lacks "where did the user come from" path.',
      'Spec §7.9 says tap-and-hold from Saved → multi-select. But what about from Results, where users have a fresh shortlist?',
      'Not in this round, but flagging: from a Results screen, a tertiary "Compare these two" button on the carousel header is a natural next-step. Worth a follow-up spec ask.'],
    ['"Subtle sign-in gate at moment of friction" is referenced but undefined.',
      '§12 mentions it; §5.2 forbids accounts in v1.',
      'Honored "no auth screens" for now. When the gate is added, the natural placement is at the Saved screen header: a single line of microcopy that does not block usage ("Want your saves on another device? Add an email — that’s the only thing it does.").'],
  ];
  return (
    <Card eyebrow="Pushback · for the build phase" title="Spec gaps I hit. Calls I made." width={1240} height={null}>
      <p style={{
        margin: '0 0 28px',
        fontFamily: ff.serif, fontSize: 16, lineHeight: '26px',
        color: fc.ink2, letterSpacing: '-0.005em', maxWidth: 820,
      }}>
        Reading the spec end-to-end against ten screens surfaced a handful of edges. Each one is
        called out below with how I handled it. Flagging now is cheaper than discovering at build.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {items.map((r, i) => (
          <div key={i} style={{
            padding: '20px 0',
            borderBottom: i < items.length - 1 ? `1px solid ${fc.line}` : 'none',
            display: 'grid', gridTemplateColumns: '36px 1fr',
            columnGap: 16, rowGap: 6,
          }}>
            <div style={{
              fontFamily: ff.display, fontStyle: 'italic',
              fontSize: 26, lineHeight: '32px', color: fc.terra, fontWeight: 400,
            }}>{i + 1}.</div>
            <div>
              <div style={{
                fontFamily: ff.display, fontStyle: 'italic',
                fontSize: 21, lineHeight: '26px', color: fc.ink,
                letterSpacing: '-0.005em', marginBottom: 8,
              }}>{r[0]}</div>
              <div style={{
                fontFamily: ff.serif, fontSize: 14, lineHeight: '22px',
                color: fc.ink2, marginBottom: 8, maxWidth: 880, letterSpacing: '-0.005em',
              }}>{r[1]}</div>
              <div style={{
                fontFamily: ff.sans, fontSize: 12, lineHeight: '18px',
                color: fc.ink, paddingLeft: 12,
                borderLeft: `2px solid ${fc.terra}`, maxWidth: 880,
              }}>
                <span className="rg-eyebrow" style={{ display: 'block', marginBottom: 4 }}>Resolution</span>
                {r[2]}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ============================================================
// OPENING NOTE
// ============================================================
function OpeningNoteCard() {
  return (
    <Card width={1240} height={null} style={{ background: fc.paperHi }}>
      <div className="rg-eyebrow" style={{ marginBottom: 14 }}>ReviewGuide · Mobile-first visual design</div>
      <h1 style={{
        margin: 0, fontFamily: ff.display, fontStyle: 'italic',
        fontSize: 64, lineHeight: '64px', letterSpacing: '-0.025em',
        color: fc.ink, fontWeight: 400, maxWidth: 980,
      }}>An editor texting you. Not a chatbot serving a query.</h1>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 40, marginTop: 32 }}>
        <p style={{
          margin: 0,
          fontFamily: ff.serif, fontSize: 17, lineHeight: '28px',
          color: fc.ink, letterSpacing: '-0.005em',
        }}>
          The brief asked for one strong direction, not a deck of variations. That direction sits below.
          Three faces of type — Instrument Serif Italic for display, Newsreader for blog body, DM Sans for
          UI. Cream paper, ink, and a muted terracotta where action lives. No purple, no sparkle, no
          gradient. Conversation is the spine; the editorial blog is the heart.
        </p>
        <p style={{
          margin: 0,
          fontFamily: ff.serif, fontSize: 17, lineHeight: '28px',
          color: fc.ink2, letterSpacing: '-0.005em',
        }}>
          Below: a foundation (color, type, components), then ten screens grouped by flow stage,
          then a log of decisions on §13’s open questions, then a few places I think the spec is
          wrong or needs sharpening. Each screen carries small annotations pointing back to the
          §13 question or §8 component it addresses.
        </p>
      </div>
    </Card>
  );
}

Object.assign(window, {
  Card, Swatch,
  ColorIdentityCard, TypeCard, ComponentLibraryCard,
  DecisionsCard, SpecFeedbackCard, OpeningNoteCard,
});
