// Design tokens for ReviewGuide.
// Loaded as a plain script before any JSX. Exports window.RG.

window.RG = (function () {
  const color = {
    // Paper / surface  (aligned with existing concept palette)
    paper:    '#FAFAF7',   // primary background — warm off-white
    paperAlt: '#F5F4F0',   // sunken surface (cards, chips inactive)
    paperHi:  '#FFFFFF',   // raised surface (bubble fill, sheet)
    // Ink
    ink:      '#1A1816',   // primary text — warm near-black
    ink2:     '#6B6560',   // secondary text
    ink3:     '#9B9590',   // tertiary / muted
    // Hairlines
    line:     '#E8E6E1',   // 1px ruled lines, dividers, borders
    line2:    '#D4D1CC',   // slightly darker (focused input, key borders)
    // Accent — muted terracotta, replaces the figma's #1B4DFF (AI-blue) per spec §11.6
    terra:    '#B8543A',
    terraSoft:'#F4E2D7',
    terraInk: '#7A3624',
    // Alt color directions explored in §13 #10
    mustard:  '#C08A2E',
    forest:   '#2B5337',
    // Functional
    saved:    '#B8543A',           // bookmark filled
    danger:   '#9B3A2D',           // destructive (reset)
  };

  const font = {
    // UI sans — matches existing concept (DM Sans).
    sans:  '"DM Sans", -apple-system, BlinkMacSystemFont, system-ui, sans-serif',
    // Editorial body serif — readable at 16/26 in long-form blog.
    serif: '"Newsreader", "Source Serif Pro", Georgia, "Times New Roman", serif',
    // Display + curious-follow-up serif (Instrument Serif Italic from existing concept).
    display: '"Instrument Serif", "Newsreader", Georgia, serif',
    mono:  '"JetBrains Mono", "SF Mono", ui-monospace, Menlo, monospace',
  };

  const radius = { sm: 6, md: 10, lg: 14, xl: 20, pill: 999 };

  const shadow = {
    card:  '0 1px 0 rgba(26,24,22,.04), 0 8px 24px -12px rgba(26,24,22,.10)',
    sheet: '0 -2px 0 rgba(26,24,22,.03), 0 -10px 30px -16px rgba(26,24,22,.12)',
  };

  // Reusable text classes (no Tailwind — single-pass CSS).
  const css = `
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&family=Newsreader:ital,opsz,wght@0,8..60,400;0,8..60,500;0,8..60,600;1,8..60,400;1,8..60,500&family=JetBrains+Mono:wght@400&display=swap');

    .rg-paper      { background: ${color.paper}; }
    .rg-paper-alt  { background: ${color.paperAlt}; }
    .rg-ink        { color: ${color.ink}; }
    .rg-ink-2      { color: ${color.ink2}; }
    .rg-ink-3      { color: ${color.ink3}; }
    .rg-terra      { color: ${color.terra}; }
    .rg-sans       { font-family: ${font.sans}; }
    .rg-serif      { font-family: ${font.serif}; }
    .rg-display    { font-family: ${font.display}; }
    .rg-mono       { font-family: ${font.mono}; }

    .rg-eyebrow {
      font-family: ${font.sans};
      font-weight: 500;
      font-size: 10px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: ${color.ink2};
    }
    .rg-hairline {
      height: 1px;
      background: ${color.line};
    }
    .rg-hairline-short {
      width: 24px; height: 1px;
      background: ${color.terra};
      opacity: .55;
    }

    /* base reset inside artboards */
    .rg-frame * { box-sizing: border-box; }
    .rg-frame { font-family: ${font.sans}; color: ${color.ink}; -webkit-font-smoothing: antialiased; }

    /* breathing dot used in loading state */
    @keyframes rg-breath {
      0%, 100% { transform: scale(1); opacity: .6; }
      50%      { transform: scale(1.35); opacity: 1; }
    }
    .rg-breath { animation: rg-breath 1.6s ease-in-out infinite; }

    /* expanding ring on bookmark tap */
    @keyframes rg-ring {
      0%   { transform: scale(.6); opacity: .6; }
      100% { transform: scale(1.6); opacity: 0; }
    }
  `;

  // inject once
  if (!document.getElementById('rg-base')) {
    const el = document.createElement('style');
    el.id = 'rg-base';
    el.textContent = css;
    document.head.appendChild(el);
  }

  return { color, font, radius, shadow };
})();
