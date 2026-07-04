import React, { useState, useRef, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Search, HelpCircle, Settings, Globe, FlameKindling, ChevronDown } from "lucide-react";

interface TopBarProps {
  isConnected: boolean;
  onHelpOpen: () => void;
  onSearchOpen?: () => void;
  currentLanguage: string;
  onLanguageChange: (lang: string) => void;
}

const routeLabels: Record<string, string> = {
  "/dashboard":            "Dashboard",
  "/projects":             "Projects",
  "/engineering":          "Engineering · Console",
  "/engineering/qomn":     "Engineering · QOMN Calculator",
  "/engineering/facp":     "Engineering · FACP Designer",
  "/engineering/guards":   "Engineering · Physics Guards",
  "/fire-alarm/designer":  "Fire Alarm · Designer",
  "/digital-twin":         "Digital Twin",
  "/digital-twin/convert": "Digital Twin · Convert",
  "/digital-twin/config":  "Digital Twin · Config",
  "/digital-twin/history": "Digital Twin · History",
  "/reports":              "Reports",
  "/elements":             "Elements",
  "/connections":          "Connections",
  "/conflicts":            "Conflicts",
  "/revit":                "BIM · Revit",
  "/revit/create":         "BIM · Revit Create",
  "/revit/elements":       "BIM · Revit Elements",
  "/autocad":              "BIM · AutoCAD",
  "/autocad/draw":         "BIM · AutoCAD Draw",
  "/settings":             "Settings",
  "/settings/advanced":    "Settings · Advanced",
  "/system-health":        "System · Health Monitor",
  "/agent-chat":           "AI · Agent Chat",
  "/exports":              "Reports · Export Manager",
  "/audit-trail":          "Reports · Audit Trail",
  "/environment/context":  "Environment · Weather",
};

const TopBar: React.FC<TopBarProps> = ({
  isConnected,
  onHelpOpen,
  onSearchOpen,
  currentLanguage,
  onLanguageChange,
}) => {
  const location = useLocation();
  const [langOpen, setLangOpen] = useState(false);
  const langRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (langRef.current && !langRef.current.contains(e.target as Node))
        setLangOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const pageLabel = routeLabels[location.pathname] ?? "BAZSPARK";
  const [section, detail] = pageLabel.includes(" · ")
    ? pageLabel.split(" · ")
    : [pageLabel, null];

  return (
    <header
      className="
        relative z-10 flex items-center h-11 shrink-0
        bg-[#0c0c10] border-b border-[#1a1a20]
        px-4 gap-0
      "
    >
      {/* Breadcrumb path */}
      <div className="flex items-center gap-1.5 text-[12px] flex-1 min-w-0">
        <span className="text-[#4a4a60] font-medium truncate">{section}</span>
        {detail && (
          <>
            <span className="text-[#2a2a38]">/</span>
            <span className="text-[#8a8a9e] font-medium truncate">{detail}</span>
          </>
        )}
      </div>

      {/* Right toolbar */}
      <div className="flex items-center gap-0.5 shrink-0">
        {/* Connection status */}
        <div className="flex items-center gap-1.5 px-3 mr-1 border-r border-[#1a1a20]">
          <span className={`baz-dot ${isConnected ? "baz-dot-online" : "baz-dot-offline"}`} />
          <span className="text-[11px] font-medium text-[#4a4a60]">
            {isConnected ? "Connected" : "Offline"}
          </span>
        </div>

        {/* Search */}
        <button
          onClick={onSearchOpen}
          aria-label="Search (Ctrl+K)"
          title="Search  Ctrl+K"
          className="
            flex items-center gap-1.5 h-7 px-2.5 rounded
            text-[#4a4a60] hover:text-[#c0c0cc] hover:bg-[#141418]
            transition-all duration-150 text-[11px]
          "
        >
          <Search size={13} strokeWidth={1.8} />
          <span className="hidden lg:inline font-medium">Search</span>
          <kbd className="hidden lg:inline bg-[#1a1a24] text-[#4a4a60] text-[9px] px-1 py-0.5 rounded border border-[#2a2a36] font-mono">⌘K</kbd>
        </button>

        {/* Help */}
        <button
          onClick={onHelpOpen}
          aria-label="Help"
          data-onboarding="help-button"
          className="
            flex items-center justify-center w-7 h-7 rounded
            text-[#4a4a60] hover:text-[#c0c0cc] hover:bg-[#141418]
            transition-all duration-150
          "
        >
          <HelpCircle size={13} strokeWidth={1.8} />
        </button>

        {/* Settings */}
        <Link
          to="/settings"
          aria-label="Settings"
          className="
            flex items-center justify-center w-7 h-7 rounded
            text-[#4a4a60] hover:text-[#c0c0cc] hover:bg-[#141418]
            transition-all duration-150
          "
        >
          <Settings size={13} strokeWidth={1.8} />
        </Link>

        {/* Language switcher */}
        <div className="relative ml-1 pl-1 border-l border-[#1a1a20]" ref={langRef}>
          <button
            onClick={() => setLangOpen(!langOpen)}
            className="
              flex items-center gap-1 h-7 px-2 rounded
              text-[#4a4a60] hover:text-[#c0c0cc] hover:bg-[#141418]
              transition-all duration-150 text-[11px] font-medium
            "
          >
            <Globe size={12} strokeWidth={1.8} />
            <span>{currentLanguage.toUpperCase()}</span>
            <ChevronDown size={10} className={`transition-transform duration-150 ${langOpen ? "rotate-180" : ""}`} />
          </button>

          {langOpen && (
            <div className="
              absolute right-0 top-full mt-1 z-50 w-28
              bg-[#111118] border border-[#222230] rounded shadow-lg
              overflow-hidden anim-scale-in
            ">
              {["en", "ar"].map(lang => (
                <button
                  key={lang}
                  onClick={() => { onLanguageChange(lang); setLangOpen(false); }}
                  className={`
                    block w-full text-left px-3 py-2 text-[12px] font-medium
                    transition-colors duration-100
                    ${currentLanguage === lang
                      ? "text-[#00d4ff] bg-[#00d4ff0a]"
                      : "text-[#8a8a9e] hover:text-[#f0f0f2] hover:bg-[#1a1a24]"}
                  `}
                >
                  {lang === "en" ? "English" : "العربية"}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default TopBar;
