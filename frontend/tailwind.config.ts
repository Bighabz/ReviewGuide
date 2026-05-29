import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        // Three blueprint faces: DM Sans (UI), Newsreader (editorial body), Instrument Serif (display)
        sans: ['var(--font-dm-sans)', 'system-ui', 'sans-serif'],
        serif: ['var(--font-newsreader)', 'Georgia', 'serif'],
        display: ['var(--font-instrument)', 'Georgia', 'serif'],
        heading: ['var(--font-instrument)', 'Georgia', 'serif'],
      },
      colors: {
        primary: {
          DEFAULT: 'var(--primary)',
          hover: 'var(--primary-hover)',
          light: 'var(--primary-light)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          hover: 'var(--accent-hover)',
          light: 'var(--accent-light)',
        },
        surface: {
          DEFAULT: 'var(--surface)',
          hover: 'var(--surface-hover)',
          elevated: 'var(--surface-elevated)',
        },
        border: {
          DEFAULT: 'var(--border)',
          strong: 'var(--border-strong)',
        },
        // ── Blueprint palette (frontend/design/lib/tokens.js) ──
        paper: {
          DEFAULT: 'var(--paper)',
          hi: 'var(--paper-hi)',
          alt: 'var(--paper-alt)',
        },
        terra: {
          DEFAULT: 'var(--terra)',
          soft: 'var(--terra-soft)',
          ink: 'var(--terra-ink)',
        },
        line: {
          DEFAULT: 'var(--line)',
          2: 'var(--line-2)',
        },
        ink: {
          DEFAULT: 'var(--ink)',
          2: 'var(--ink-2)',
          3: 'var(--ink-3)',
        },
        'ink-secondary': 'var(--text-secondary)',
        'ink-muted': 'var(--text-muted)',
      },
      boxShadow: {
        'float': 'var(--shadow-float)',
        'premium': 'var(--gpt-shadow-premium)',
        'card': 'var(--shadow-card)',
        'card-hover': '0 4px 12px rgba(26,24,22,0.08), 0 12px 28px rgba(26,24,22,0.06)',
        'editorial': '0 2px 8px rgba(26,24,22,0.06)',
        // Blueprint component shadows
        'rg-card': 'var(--shadow-card)',
        'rg-sheet': 'var(--shadow-sheet)',
      },
      borderRadius: {
        'editorial': '0.625rem',
        // Blueprint radius scale: sm 6 / md 10 / lg 14 / xl 20 / pill 999
        '6': '6px',
        '10': '10px',
        '14': '14px',
        '20': '20px',
        'pill': '999px',
      },
      animation: {
        'fade-up': 'fadeUp 0.5s ease-out forwards',
        'slide-in': 'slideIn 0.3s ease-out forwards',
        // RFC §2.6 — card entrance animation
        'card-enter': 'card-enter 200ms ease-out',
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideIn: {
          '0%': { opacity: '0', transform: 'translateX(-8px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        // RFC §2.6 — card entrance keyframes
        'card-enter': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      // RFC §2.6 — named duration utilities for streaming / skeleton / card transitions
      transitionDuration: {
        'stream': '150ms',
        'skeleton': '200ms',
        'card': '200ms',
      },
      // RFC §2.6 — named easing utilities for streaming state transitions
      transitionTimingFunction: {
        'stream-out': 'ease-out',
        'stream-inout': 'ease-in-out',
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
export default config
