import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "var(--color-primary)",
        secondary: "var(--color-secondary)",
        background: "var(--color-background)",
        surface: "var(--color-surface)",
        muted: "var(--color-muted)",
        accent: "var(--color-accent)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        full: "var(--radius)",
      },
      spacing: {
        "1": "var(--spacing-unit)",
        "2": "calc(var(--spacing-unit) * 2)",
        "3": "calc(var(--spacing-unit) * 3)",
        "4": "calc(var(--spacing-unit) * 4)",
        "5": "calc(var(--spacing-unit) * 5)",
        "6": "calc(var(--spacing-unit) * 6)",
        "8": "calc(var(--spacing-unit) * 8)",
        "10": "calc(var(--spacing-unit) * 10)",
        "12": "calc(var(--spacing-unit) * 12)",
        "16": "calc(var(--spacing-unit) * 16)",
        "20": "calc(var(--spacing-unit) * 20)",
      },
      fontSize: {
        base: "var(--font-base)",
        medium: "var(--font-medium)",
        large: "var(--font-large)",
        xl: "var(--font-xl)",
        "2xl": "var(--font-xxl)",
      },
    },
  },
  plugins: [],
} satisfies Config;