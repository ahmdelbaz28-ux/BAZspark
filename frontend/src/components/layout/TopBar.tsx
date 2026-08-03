import { Globe, HelpCircle, Search, Settings, Sun, Moon } from "lucide-react";
import type React from "react";
import { memo, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router";
import { UserMenu } from "@/components/auth/UserMenu";
import { ContextualHelpButton } from "@/components/shared/ContextualHelpButton";
import { useTheme } from "@/contexts/ThemeContext";
import { BazSparkLogo } from "@/components/auth/BazSparkLogo";

interface TopBarProps {
        isConnected: boolean;
        onHelpOpen: () => void;
        onSearchOpen?: () => void;
        currentLanguage: string;
        onLanguageChange: (lang: string) => void;
}

const routeLabels: Record<string, string> = {
        "/": "Dashboard",
        "/projects": "Projects",
        "/engineering": "Engineering",
        "/fire-alarm-designer": "Fire Alarm Designer",
        "/fire-alarm/designer": "Fire Alarm Designer",
        "/digital-twin": "Digital Twin",
        "/reports": "Reports",
        "/elements": "Elements",
        "/connections": "Connections",
        "/conflicts": "Conflicts",
        "/settings": "Settings",
        "/autocad": "AutoCAD",
        "/autocad/draw": "ACAD Draw",
        "/revit": "Revit",
        "/revit/create": "Revit Create",
        "/revit/elements": "Revit Elements",
        "/digital-twin/convert": "DT Convert",
        "/digital-twin/config": "DT Config",
        "/digital-twin/history": "DT History",
};

/**
 * Shared className for icon-only TopBar buttons.
 * UI/UX Pro Max audit (Phase 5.1):
 *   - `cursor-pointer` per checklist
 *   - `focus-visible:ring-2` for keyboard navigation
 *   - `transition-[color,background-color,border-color,box-shadow]` (no transform — avoids layout shift)
 *   - `hover:-translate-y-px` is intentionally NOT used here because shifting
 *     TopBar icons causes the entire 16px row to reflow on hover. We use a
 *     color-only hover treatment instead.
 */
const iconButtonClass =
        "p-2 rounded-lg text-muted-foreground cursor-pointer transition-[color,background-color] duration-200 " +
        "hover:text-cyan-300 hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 " +
        "focus-visible:ring-cyan-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background";

const TopBar: React.FC<TopBarProps> = memo(
        // NOSONAR - typescript:S9011: Intentionally complex demo UI with many interactive buttons
        ({ isConnected, onHelpOpen, onSearchOpen, currentLanguage, onLanguageChange }) => {
                const location = useLocation();
                const { dark, toggle } = useTheme();
                const [langOpen, setLangOpen] = useState(false);
                const langRef = useRef<HTMLDivElement>(null);

                // Close language dropdown on outside click
                useEffect(() => {
                        const handler = (e: MouseEvent) => {
                                if (langRef.current && !langRef.current.contains(e.target as Node)) {
                                        setLangOpen(false);
                                }
                        };
                        document.addEventListener("mousedown", handler);
                        return () => document.removeEventListener("mousedown", handler);
                }, []);

                const pageName = routeLabels[location.pathname] || "BAZSPARK";

                return (
                        <header
                                className="h-16 glass flex items-center px-4 lg:px-6 gap-2 lg:gap-4 shrink-0 sticky top-0 z-40"
                                style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}
                        >
                                {/* Left — logo + page title */}
                                <div className="flex items-center gap-3 min-w-0">
                                        <BazSparkLogo size={30} className="shrink-0" />
                                        <h1 className="text-foreground font-semibold text-[16px] tracking-tight truncate ml-1">
                                                {pageName}
                                        </h1>
                                </div>

                                <div className="flex-1" />

                                {/* Connection status — neutral slate when offline, no red */}
                                <div
                                        className="flex items-center gap-2"
                                        role="status"
                                        aria-live="polite"
                                >
                                        <span
                                                className={`h-2 w-2 rounded-full ${isConnected ? "bg-success" : "bg-slate-500"}`}
                                                aria-hidden="true"
                                        />
                                        <span className="text-muted-foreground text-[13px] hidden md:inline">
                                                {isConnected ? "Online" : "Offline"}
                                        </span>
                                </div>

                                <div className="h-5 w-px bg-white/10" role="separator" aria-orientation="vertical" />

                                {/* Action buttons */}
                                <button
                                        type="button"
                                        onClick={onSearchOpen}
                                        className={iconButtonClass}
                                        aria-label="Search"
                                        title="Search (Ctrl+K)"
                                >
                                        <Search aria-hidden="true" className="h-[18px] w-[18px]" />
                                </button>

                                <ContextualHelpButton />

                                <button
                                        type="button"
                                        onClick={onHelpOpen}
                                        className={iconButtonClass}
                                        aria-label="Help"
                                        data-onboarding="help-button"
                                        title="Global help (F1)"
                                >
                                        <HelpCircle aria-hidden="true" className="h-[18px] w-[18px]" />
                                </button>

                                <Link
                                        to="/settings"
                                        className={iconButtonClass}
                                        aria-label="Settings"
                                        title="Settings"
                                >
                                        <Settings aria-hidden="true" className="h-[18px] w-[18px]" />
                                </Link>

                                {/* Dark mode toggle */}
                                <button
                                        type="button"
                                        onClick={toggle}
                                        aria-label="Toggle dark mode"
                                        className={iconButtonClass}
                                >
                                        {dark ? (
                                                <Moon aria-hidden="true" className="h-5 w-5" />
                                        ) : (
                                                <Sun aria-hidden="true" className="h-5 w-5" />
                                        )}
                                </button>

                                {/* Language selector */}
                                <div className="relative" ref={langRef}>
                                        <button
                                                type="button"
                                                onClick={() => setLangOpen(!langOpen)}
                                                className="flex items-center gap-1.5 px-3 py-2 text-muted-foreground cursor-pointer hover:text-cyan-300 hover:bg-white/5 transition-[color,background-color] duration-200 text-[13px] rounded-lg border border-white/10 font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                                                aria-label="Change language"
                                                aria-expanded={langOpen}
                                                aria-haspopup="menu"
                                        >
                                                <Globe aria-hidden="true" className="h-4 w-4" />
                                                {currentLanguage.toUpperCase()}
                                        </button>
                                        {langOpen && (
                                                <div
                                                        className="absolute right-0 top-full mt-2 glass rounded-lg shadow-xl z-50 min-w-[120px] overflow-hidden border border-white/10"
                                                        role="menu"
                                                        aria-label="Language selector"
                                                >
                                                        {["en", "ar"].map((lang) => (
                                                                <button
                                                                        type="button"
                                                                        key={lang}
                                                                        onClick={() => {
                                                                                onLanguageChange(lang);
                                                                                setLangOpen(false);
                                                                        }}
                                                                        role="menuitemradio"
                                                                        aria-checked={currentLanguage === lang}
                                                                        className={`block w-full text-left px-3 py-2.5 text-[13px] cursor-pointer transition-colors duration-200 ${
                                                                                currentLanguage === lang
                                                                                        ? "text-cyan-300 bg-cyan-400/10"
                                                                                        : "text-foreground hover:bg-white/5"
                                                                        }`}
                                                                >
                                                                        {lang === "en" ? "English" : "العربية"}
                                                                </button>
                                                        ))}
                                                </div>
                                        )}
                                </div>

                                <div className="h-5 w-px bg-white/10" role="separator" aria-orientation="vertical" />

                                <UserMenu />
                        </header>
                );
        },
);

TopBar.displayName = "TopBar";

export default TopBar;
