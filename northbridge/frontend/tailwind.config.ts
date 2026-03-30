import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'nb-bg': '#090e1a',
        'nb-surface': '#0f1729',
        'nb-surface2': '#162035',
        'nb-border': '#1e2d45',
        'nb-accent': {
          DEFAULT: '#2563eb',
          dark: '#1d4ed8',
        },
        'nb-gold': {
          DEFAULT: '#d97706',
          dark: '#b45309',
        },
        'nb-green': {
          DEFAULT: '#10b981',
          dark: '#047857',
        },
        'nb-red': {
          DEFAULT: '#ef4444',
          dark: '#b91c1c',
        },
        'nb-text': '#e2e8f0',
        'nb-muted': '#64748b',
        'nb-subtle': '#94a3b8',
      },
      fontFamily: {
        sans: [
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          '"Helvetica Neue"',
          'Arial',
          'sans-serif',
        ],
        mono: [
          '"JetBrains Mono"',
          '"Fira Code"',
          '"Cascadia Code"',
          'Consolas',
          'monospace',
        ],
      },
      borderColor: {
        DEFAULT: '#1e2d45',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
      },
      screens: {
        xs: '480px',
      },
    },
  },
  plugins: [],
}

export default config
