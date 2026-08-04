// BAZspark Design System Tokens (DM-1 Deep Cyan)

export const colors = {
  primary: {
    50: '#ecfeff',
    100: '#cffafe',
    200: '#a5f3fc',
    300: '#67e8f9',
    400: '#22d3ee', // Primary brand color
    500: '#06b6d4',
    600: '#0891b2',
    700: '#0e7490',
    800: '#155e75',
    900: '#164e63',
    950: '#083344',
  },
  secondary: { // Amber for non-critical warnings
    50: '#fffbeb',
    500: '#f59e0b',
    950: '#451a03',
  },
  success: '#10b981', // Emerald 500
  error: '#ef4444',   // Red 500
  warning: '#f59e0b', // Amber 500
  info: '#0ea5e9',    // Sky 500
  neutral: { // Slate
    50: '#f8fafc',
    100: '#f1f5f9',
    200: '#e2e8f0',
    300: '#cbd5e1',
    400: '#94a3b8',
    500: '#64748b',
    600: '#475569',
    700: '#334155',
    800: '#1e293b',
    900: '#0f172a',
    950: '#020617',
  }
};

export const typography = {
  fonts: {
    arabic: '"Noto Sans Arabic", sans-serif',
    english: '"Inter", sans-serif',
    mono: '"JetBrains Mono", monospace'
  },
  scale: {
    caption: '10pt',
    small: '12pt',
    body: '14pt',
    large: '18pt',
    h4: '22pt',
    h3: '28pt',
    h2: '35pt',
    h1: '44pt',
    display: '55pt'
  }
};

export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '16px',
  lg: '24px',
  xl: '32px',
  '2xl': '48px',
  '3xl': '64px'
};

export const borderRadius = {
  sm: '4px',
  md: '8px',
  lg: '12px',
  xl: '16px',
  full: '9999px'
};

export const transitions = {
  fast: '150ms cubic-bezier(0.4, 0, 0.2, 1)',
  normal: '200ms cubic-bezier(0.4, 0, 0.2, 1)',
  slow: '300ms cubic-bezier(0.4, 0, 0.2, 1)',
};
