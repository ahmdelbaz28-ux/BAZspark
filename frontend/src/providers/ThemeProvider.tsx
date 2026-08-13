import type React from "react";
import { createContext, useContext, useEffect, useState } from "react";

export type VisualMode = "industrial" | "scada" | "marine" | "facp";

interface ThemeContextType {
	mode: VisualMode;
	setMode: (mode: VisualMode) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
	const [mode, setModeState] = useState<VisualMode>(() => {
		const saved = localStorage.getItem("bazspark-visual-mode");
		return (saved as VisualMode) || "industrial";
	});

	useEffect(() => {
		document.body.setAttribute("data-mode", mode);
	}, [mode]);

	const setMode = (newMode: VisualMode) => {
		setModeState(newMode);
		localStorage.setItem("bazspark-visual-mode", newMode);
	};

	return (
		<ThemeContext.Provider value={{ mode, setMode }}>
			{children}
		</ThemeContext.Provider>
	);
}

export function useTheme() {
	const context = useContext(ThemeContext);
	if (context === undefined) {
		throw new Error("useTheme must be used within a ThemeProvider");
	}
	return context;
}
