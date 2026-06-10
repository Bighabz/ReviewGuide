import type { Config } from 'tailwindcss'

const config: Config = {
  // Dark mode follows the app's [data-theme] toggle, not the OS preference —
  // without this, every `dark:` variant compiles to prefers-color-scheme and
  // ignores the in-app theme switch.
  darkMode: ['class', '[data-theme="dark"]'],
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-dm-sans)', 'system-ui', 'sans-serif'],
        heading: ['var(--font-instrument)', 'Georgia', 'serif'],
        serif: ['var(--font-instrument)', 'Georgia', 'serif'],
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
        ink: 'var(--text)',
        'ink-secondary': 'var(--text-secondary)',
        'ink-muted': 'var(--text-muted)',
      },
      boxShadow: {
        'float': 'var(--shadow-float)',
        'premium': 'var(--gpt-shadow-premium)',
        'card': '0 1px 3px rgba(0,0,0,0.04), 0 6px 16px rgba(0,0,0,0.04)',
        'card-hover': '0 4px 12px rgba(0,0,0,0.08), 0 12px 28px rgba(0,0,0,0.06)',
        'editorial': '0 2px 8px rgba(28,25,23,0.06)',
      },
      borderRadius: {
        'editorial': '0.625rem',
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
