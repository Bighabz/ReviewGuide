// Print composition — renders all artboards in plain stacked flow (no canvas chrome).
// v2 delta first, then v1 reference. Matches the order in the design canvas.

function PrintLayout() {
  const sections = [
    // ---------- v2 DELTA ----------
    { title: 'v2 — delta', subtitle: 'Logo + Discover + new components · sits on top of the locked v1 system',
      items: [
        { label: 'What changed',                        node: <V2OpeningCard /> },
        { label: 'Logo system · two treatments',        node: <LogoSystemCard /> },
        { label: 'Tagline rotation · spec for build',   node: <RotationSpecCard /> },
        { label: 'Transitional reasoning bubble · new', node: <TransitionalBubbleCard /> },
      ] },

    { title: 'v2 — updated screens',
      subtitle: 'Headers, Discover, About-you reverts to MVP empty (populated deferred post-MVP)',
      items: [
        { label: 'Discover (with bubble hero)',                              node: <DiscoverScreen />,      mobile: true },
        { label: 'Chat — quiz path with reasoning bubble',                   node: <ChatQuizV2Screen />,    mobile: true },
        { label: 'About you · MVP empty state (populated deferred post-MVP)', node: <ProfileScreen />,       mobile: true },
      ] },

    // ---------- v1 LOCKED SYSTEM ----------
    { title: 'v1 — locked system',
      subtitle: 'Opening note from the original pass',
      items: [{ label: 'Opening note', node: <OpeningNoteCard /> }] },

    { title: '00 — System', subtitle: 'Color, type, components — defined once, used everywhere',
      items: [
        { label: 'Color identity · three directions', node: <ColorIdentityCard /> },
        { label: 'Type system · three faces',         node: <TypeCard /> },
        { label: 'Component library · spec §8',       node: <ComponentLibraryCard /> },
      ] },

    { title: '02 — Chat', subtitle: 'Empty / fast / quiz / loading · spec §7.2–§7.4, §7.7 · with v2 headers',
      items: [
        { label: 'Chat — empty',               node: <ChatEmptyScreen />, mobile: true },
        { label: 'Chat — fast path · loading', node: <ChatFastScreen />,  mobile: true },
        { label: 'Chat — quiz path (v1)',      node: <ChatQuizScreen />,  mobile: true },
        { label: 'Loading detail · §13 #1',    node: <LoadingScreen />,   mobile: true },
      ] },

    { title: '03 — Results', subtitle: "The product's payload · spec §7.5 · with budget-first turn + reasoning bubble",
      items: [{ label: 'Results (full scroll)', node: <ResultsScreen />, mobile: true }] },

    { title: '04 — Product detail', subtitle: "Spec §7.6 · the AI's take + prose specs + honest notes",
      items: [{ label: 'Product detail (full scroll)', node: <ProductDetailScreen />, mobile: true }] },

    { title: '05 — Saved & Compare', subtitle: 'Spec §7.8 · §7.9',
      items: [
        { label: 'Saved',       node: <SavedScreen />,   mobile: true },
        { label: 'Compare two', node: <CompareScreen />, mobile: true },
      ] },

    { title: '06 — About you · post-MVP', subtitle: 'Populated state · deferred reference, not the MVP build',
      items: [{ label: 'About you · populated (post-MVP target)', node: <ProfileScreenFull />, mobile: true }] },

    { title: '07 — Decisions & spec feedback', subtitle: 'Open §13 questions answered · pushback for build',
      items: [
        { label: 'Decisions log · all 10 §13 questions', node: <DecisionsCard /> },
        { label: 'Spec feedback',                        node: <SpecFeedbackCard /> },
      ] },
  ];

  return (
    <div className="print-root">
      {sections.map((s, si) => (
        <React.Fragment key={si}>
          <section className="print-section-head">
            <div className="print-eyebrow">Section {String(si).padStart(2,'0')}</div>
            <h2 className="print-section-title">{s.title}</h2>
            <div className="print-section-sub">{s.subtitle}</div>
          </section>
          {s.items.map((it, ii) => (
            <article key={ii} className={'print-artboard' + (it.mobile ? ' is-mobile' : '')}>
              <div className="print-artboard-label">{it.label}</div>
              <div className="print-artboard-body">{it.node}</div>
            </article>
          ))}
        </React.Fragment>
      ))}
    </div>
  );
}

const printRoot = ReactDOM.createRoot(document.getElementById('root'));
printRoot.render(<PrintLayout />);

// Trigger print after fonts + render settle.
(async () => {
  if (window.__rg_no_print) return;
  try { if (document.fonts && document.fonts.ready) await document.fonts.ready; } catch (e) {}
  await new Promise(r => setTimeout(r, 900));
  window.print();
})();
