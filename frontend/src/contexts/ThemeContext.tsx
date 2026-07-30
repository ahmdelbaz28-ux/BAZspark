import { createContext, useCallback, useContext, useEffect, useState, useMemo, ReactNode } from "react";

interface Theme {
  readonly dark: boolean;
  readonly toggle: () => void;
}

const ThemeContext = createContext<Theme | null>(null);

export function ThemeProvider({ children }: { readonly children: ReactNode }) {
  const [dark, setDark] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem("dark");
      return stored === "true" || (!stored && window.matchMedia("(prefers-color-scheme: dark)").matches);
    } catch {
      return window.matchMedia("(prefers-color-scheme: dark)").matches;
    }
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("dark", dark.toString());
    } catch {
      // Storage unavailable
    }
  }, [dark]);

  const toggle = useCallback(() => setDark((prev) => !prev), []);

  const contextValue = useMemo(() => ({ dark, toggle }), [dark, toggle]);

  return (
    <ThemeContext.Provider value={contextValue}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}