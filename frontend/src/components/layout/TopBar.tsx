import { Globe, HelpCircle, Search, Settings, Sun, Moon } from "lucide-react";
import type React from "react";
import { memo, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router";
import { UserMenu } from "@/components/auth/UserMenu";
import { ContextualHelpButton } from "@/components/shared/ContextualHelpButton";
import { useTheme } from "@/contexts/ThemeContext";
import { BazSparkLogo } from "@/components/auth/BazSparkLogo";
import "@/styles/shell.css";

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
                const connState = isConnected ? "online" : "offline";

                return (
                        <header
                                className="shell-topbar h-16 flex items-center px-4 lg:px-6 gap-2 lg:gap-4 shrink-0 sticky top-0 z-40"
                        >
                                {/* Left — logo + page title */}
                                <div className="flex items-center gap-3 min-w-0">
                                        <BazSparkLogo size={30} className="shrink-0" />
                                        <h1 className="shell-page-title truncate" title={pageName}>
                                                {pageName}
                                        </h1>
                                </div>

                                <div className="flex-1" />

                                {/* Connection status — alarm-color vocabulary (evac-green / amber-alert).
                                    Previous bg-slate-500 was a decorative nothing; amber = TROUBLE in FACP. */}
                                <div
                                        className="flex items-center gap-2"
                                        role="status"
                                        aria-live="polite"
                                        aria-label={isConnected ? "Connected to backend" : "Disconnected from backend"}
                                >
                                        <span
                                                className={`shell-conn-dot ${connState}`}
                                                aria-hidden="true"
                                        />
                                        <span className={`shell-conn-label ${connState} hidden md:inline`}>
                                                {isConnected ? "Online" : "Offline"}
                                        </span>
                                </div>

                                <hr className="shell-separator" aria-orientation="vertical" />

                                {/* Action buttons */}
                                <button
                                        type="button"
                                        onClick={onSearchOpen}
                                        className="shell-icon-btn p-2"
                                        aria-label="Search"
                                        title="Search (Ctrl+K)"
                                >
                                        <Search aria-hidden="true" className="h-[18px] w-[18px]" />
                                </button>

                                <ContextualHelpButton />

                                <button
                                        type="button"
                                        onClick={onHelpOpen}
                                        className="shell-icon-btn p-2"
                                        aria-label="Help"
                                        data-onboarding="help-button"
                                        title="Global help (F1)"
                                >
                                        <HelpCircle aria-hidden="true" className="h-[18px] w-[18px]" />
                                </button>

                                <Link
                                        to="/settings"
                                        className="shell-icon-btn p-2 inline-flex"
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
                                        className="shell-icon-btn p-2"
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
                                                className="shell-lang-btn flex items-center gap-1.5 px-3 py-2"
                                                aria-label="Change language"
                                                aria-expanded={langOpen}
                                                aria-haspopup="menu"
                                        >
                                                <Globe aria-hidden="true" className="h-4 w-4" />
                                                {currentLanguage.toUpperCase()}
                                        </button>
                                        {langOpen && (
                                                <div
                                                        className="shell-lang-menu absolute right-0 top-full mt-2 shadow-xl z-50 min-w-[140px] overflow-hidden"
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
                                                                        className={`shell-lang-item block w-full text-left px-3 py-2.5 ${
                                                                                currentLanguage === lang ? "active" : ""
                                                                        }`}
                                                                >
                                                                        {lang === "en" ? "English" : "العربية"}
                                                                </button>
                                                        ))}
                                                </div>
                                        )}
                                </div>

                                <hr className="shell-separator" aria-orientation="vertical" />

                                <UserMenu />
                        </header>
                );
        },
);

TopBar.displayName = "TopBar";

export default TopBar;
