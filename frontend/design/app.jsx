// Root composition for the ReviewGuide design canvas.
// v1 (the locked first pass) + v2 delta section at the top.

function App() {
  return (
    <DesignCanvas>

      {/* ============================================================ */}
      <DCSection id="v2-intro" title="v2 — delta" subtitle="Logo + Discover update + new components · sits on top of locked v1 system">
        <DCArtboard id="v2-opening" label="What changed" width={1280} height={460}>
          <V2OpeningCard />
        </DCArtboard>
        <DCArtboard id="logo-system" label="Logo system · two treatments" width={1280} height={null}>
          <LogoSystemCard />
        </DCArtboard>
        <DCArtboard id="rotation-spec" label="Tagline rotation · spec for build" width={1280} height={null}>
          <RotationSpecCard />
        </DCArtboard>
        <DCArtboard id="transitional-bubble" label="Transitional reasoning bubble · new component" width={1280} height={null}>
          <TransitionalBubbleCard />
        </DCArtboard>
      </DCSection>

      {/* ============================================================ */}
      <DCSection id="v2-screens" title="v2 — updated screens" subtitle="Surfaces that moved · headers, Discover, About-you reverts to MVP empty (populated version deferred post-MVP)">
        <DCArtboard id="discover-v2" label="Discover (with bubble hero)" width={390} height={1240}>
          <DiscoverScreen />
        </DCArtboard>
        <DCArtboard id="quiz-v2" label="Chat — quiz path with reasoning bubble" width={390} height={1020}>
          <ChatQuizV2Screen />
        </DCArtboard>
        <DCArtboard id="about-mvp" label="About you · MVP empty state (populated deferred post-MVP)" width={390} height={920}>
          <ProfileScreen />
        </DCArtboard>
      </DCSection>

      {/* ============================================================ */}
      <DCSection id="intro" title="v1 — locked system" subtitle="One direction · ten screens · annotated · stays as-is">
        <DCArtboard id="opening" label="Opening note" width={1280} height={420}>
          <OpeningNoteCard />
        </DCArtboard>
      </DCSection>

      <DCSection id="system" title="00 — System" subtitle="Color, type, components — defined once, used everywhere">
        <DCArtboard id="color" label="Color identity · 3 directions" width={1280} height={760}>
          <ColorIdentityCard />
        </DCArtboard>
        <DCArtboard id="type" label="Type system · three faces" width={1280} height={820}>
          <TypeCard />
        </DCArtboard>
        <DCArtboard id="components" label="Component library · spec §8" width={1280} height={1900}>
          <ComponentLibraryCard />
        </DCArtboard>
      </DCSection>

      <DCSection id="chat" title="02 — Chat" subtitle="Empty / fast / quiz · with v2 headers">
        <DCArtboard id="chat-empty" label="Chat — empty" width={390} height={844}>
          <ChatEmptyScreen />
        </DCArtboard>
        <DCArtboard id="chat-fast" label="Chat — fast path · loading" width={390} height={844}>
          <ChatFastScreen />
        </DCArtboard>
        <DCArtboard id="chat-quiz" label="Chat — quiz path (v1, for reference)" width={390} height={920}>
          <ChatQuizScreen />
        </DCArtboard>
        <DCArtboard id="chat-loading" label="Loading detail · §13 #1" width={390} height={844}>
          <LoadingScreen />
        </DCArtboard>
      </DCSection>

      <DCSection id="results" title="03 — Results" subtitle="With v2 wordmark header">
        <DCArtboard id="results-full" label="Results (full scroll)" width={390} height={2900}>
          <ResultsScreen />
        </DCArtboard>
      </DCSection>

      <DCSection id="detail" title="04 — Product detail" subtitle="With v2 wordmark header">
        <DCArtboard id="product-detail" label="Product detail" width={390} height={1380}>
          <ProductDetailScreen />
        </DCArtboard>
      </DCSection>

      <DCSection id="saved-compare" title="05 — Saved & Compare" subtitle="With v2 wordmark header">
        <DCArtboard id="saved" label="Saved" width={390} height={1120}>
          <SavedScreen />
        </DCArtboard>
        <DCArtboard id="compare" label="Compare two" width={390} height={1240}>
          <CompareScreen />
        </DCArtboard>
      </DCSection>

      <DCSection id="profile-post-mvp" title="06 — About you · post-MVP" subtitle="Populated state · deferred reference">
        <DCArtboard id="profile-full" label="About you · populated (post-MVP target)" width={390} height={1320}>
          <ProfileScreenFull />
        </DCArtboard>
      </DCSection>

      <DCSection id="decisions" title="07 — Decisions & spec feedback" subtitle="From v1 · still in force">
        <DCArtboard id="decisions-log" label="Decisions log" width={1280} height={null}>
          <DecisionsCard />
        </DCArtboard>
        <DCArtboard id="spec-feedback" label="Spec feedback" width={1280} height={null}>
          <SpecFeedbackCard />
        </DCArtboard>
      </DCSection>

    </DesignCanvas>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
