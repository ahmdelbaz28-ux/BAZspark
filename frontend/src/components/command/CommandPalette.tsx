
import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { HELP_TOPICS } from "@/help/helpTopics";
import { cn } from "@/lib/utils";

export interface CommandItem {
        id: string;
        label: string;
        shortcut?: string;
        icon?: React.ReactNode;
        category: "navigation" | "action" | "help";
        path?: string;
        helpTopicId?: string;
}

const COMMANDS: CommandItem[] = [
        {
                id: "cmd-dashboard",
                label: "Open Dashboard",
                shortcut: "G D",
                category: "navigation",
                path: "/dashboard",
        },
        {
                id: "cmd-projects",
                label: "Open Projects",
                shortcut: "G P",
                category: "navigation",
                path: "/projects",
        },
        {
                id: "cmd-engineering",
                label: "Open Engineering",
                shortcut: "G E",
                category: "navigation",
                path: "/engineering",
        },
        {
                id: "cmd-fire-alarm-designer",
                label: "Open Fire Alarm Designer",
                shortcut: "G F",
                category: "navigation",
                path: "/fire-alarm/designer",
        },
        {
                id: "cmd-digital-twin",
                label: "Open Digital Twin",
                shortcut: "G T",
                category: "navigation",
                path: "/digital-twin",
        },
        {
                id: "cmd-reports",
                label: "Open Reports",
                shortcut: "G R",
                category: "navigation",
                path: "/reports",
        },
        {
                id: "cmd-facp",
                label: "Open FACP Selection",
                category: "navigation",
                path: "/facp",
        },
        {
                id: "cmd-marine",
                label: "Open Marine Fire Safety",
                category: "navigation",
                path: "/marine",
        },
        {
                id: "cmd-mining",
                label: "Open Mining Safety",
                category: "navigation",
                path: "/mining",
        },
        {
                id: "cmd-autocad",
                label: "Open AutoCAD Integration",
                category: "navigation",
                path: "/autocad",
        },
        {
                id: "cmd-revit",
                label: "Open Revit Integration",
                category: "navigation",
                path: "/revit",
        },
        {
                id: "cmd-etap",
                label: "Open ETAP Integration",
                category: "navigation",
                path: "/etap",
        },
        {
                id: "cmd-environment",
                label: "Open Environment",
                category: "navigation",
                path: "/environment",
        },
        {
                id: "cmd-monitor",
                label: "Open System Monitor",
                category: "navigation",
                path: "/monitor",
        },
        {
                id: "cmd-memory",
                label: "Open Memory Store",
                category: "navigation",
                path: "/memory",
        },
        {
                id: "cmd-workflow",
                label: "Open Workflow",
                category: "navigation",
                path: "/workflow",
        },
        {
                id: "cmd-elements",
                label: "Open BIM Elements",
                category: "navigation",
                path: "/elements",
        },
        {
                id: "cmd-connections",
                label: "Open Connections",
                category: "navigation",
                path: "/connections",
        },
        {
                id: "cmd-conflicts",
                label: "Open Conflicts",
                category: "navigation",
                path: "/conflicts",
        },
        {
                id: "cmd-graphrag",
                label: "Open GraphRAG",
                category: "navigation",
                path: "/graphrag",
        },
        {
                id: "cmd-bim-providers",
                label: "Open BIM Providers",
                category: "navigation",
                path: "/bim-providers",
        },
        {
                id: "cmd-exports",
                label: "Open Exports",
                category: "navigation",
                path: "/exports",
        },
        {
                id: "cmd-self-healing",
                label: "Open Self-Healing",
                category: "navigation",
                path: "/self-healing",
        },
        {
                id: "cmd-fds-simulation",
                label: "Open FDS Simulation",
                category: "navigation",
                path: "/fds-simulation",
        },
        {
                id: "cmd-ifc43-mapping",
                label: "Open IFC 4.3 Mapping",
                category: "navigation",
                path: "/ifc43-mapping",
        },
        {
                id: "cmd-topology",
                label: "Open Topology Graph",
                category: "navigation",
                path: "/topology",
        },
        {
                id: "cmd-ar-export",
                label: "Open AR Export",
                category: "navigation",
                path: "/ar-export",
        },
        {
                id: "cmd-webhook-management",
                label: "Open Webhook Management",
                category: "navigation",
                path: "/webhook-management",
        },
        {
                id: "cmd-generative-design",
                label: "Open Generative Design",
                category: "navigation",
                path: "/generative-design",
        },
        {
                id: "cmd-create-project",
                label: "Create New Project",
                shortcut: "N C",
                category: "action",
                path: "/projects",
        },
        {
                id: "cmd-generate-report",
                label: "Generate Report",
                shortcut: "N R",
                category: "action",
                path: "/reports",
        },
        {
                id: "cmd-run-smoke-spacing",
                label: "Run Smoke Spacing Calculation",
                category: "action",
                path: "/engineering",
        },
        {
                id: "cmd-run-heat-spacing",
                label: "Run Heat Spacing Calculation",
                category: "action",
                path: "/engineering",
        },
        {
                id: "cmd-place-detectors",
                label: "Place Detectors in Room",
                category: "action",
                path: "/engineering",
        },
        {
                id: "cmd-run-room-analysis",
                label: "Run Room Analysis",
                category: "action",
                path: "/engineering",
        },
        {
                id: "cmd-facp-verify",
                label: "Verify FACP Compliance",
                category: "action",
                path: "/facp",
        },
        {
                id: "cmd-facp-schedule",
                label: "Generate FACP Schedule",
                category: "action",
                path: "/facp",
        },
        {
                id: "cmd-compliance-narrative",
                label: "Generate Compliance Narrative",
                category: "action",
                path: "/reports",
        },
        {
                id: "cmd-settings",
                label: "Open Settings",
                shortcut: "G S",
                category: "navigation",
                path: "/settings",
        },
        {
                id: "cmd-cad-settings",
                label: "Open CAD Settings",
                category: "navigation",
                path: "/settings/cad",
        },
        {
                id: "cmd-api-keys",
                label: "Open API Keys",
                category: "navigation",
                path: "/api-keys",
        },
        {
                id: "cmd-database-admin",
                label: "Open Database Admin",
                category: "navigation",
                path: "/settings/database",
        },
        {
                id: "cmd-help",
                label: "Open Help",
                shortcut: "?",
                category: "help",
                helpTopicId: "dashboard.overview",
        },
];

type CommandPaletteSearchResult = {
        type: "command";
        item: CommandItem;
};

type HelpSearchResult = {
        type: "help";
        item: (typeof HELP_TOPICS)[keyof typeof HELP_TOPICS];
};

type PaletteItem = CommandPaletteSearchResult | HelpSearchResult;

interface CommandPaletteProps {
        open: boolean;
        onOpenChange: (open: boolean) => void;
}

const CommandPalette: React.FC<CommandPaletteProps> = ({
        open,
        onOpenChange,
}) => {
        const [query, setQuery] = useState("");
        const [selectedIndex, setSelectedIndex] = useState(0);
        const inputRef = useRef<HTMLInputElement>(null);
        const listRef = useRef<HTMLDivElement>(null);
        const navigate = useNavigate();

        const results: PaletteItem[] = (() => {
                const q = query.trim().toLowerCase();
                if (!q) {
                        return COMMANDS.map((item) => ({ type: "command" as const, item }));
                }

                const matchedCommands = COMMANDS.filter((item) =>
                        item.label.toLowerCase().includes(q),
                );
                const matchedHelp = Object.values(HELP_TOPICS).filter((topic) =>
                        [
                                topic.titleEn,
                                topic.titleAr,
                                topic.descriptionEn,
                                topic.descriptionAr,
                                topic.id,
                        ].some((value) => value.toLowerCase().includes(q)),
                );

                return [
                        ...matchedCommands.map((item) => ({ type: "command" as const, item })),
                        ...matchedHelp.map((item) => ({ type: "help" as const, item })),
                ];
        })();

        useEffect(() => {
                if (open) {
                        setQuery("");
                        setSelectedIndex(0);
                        setTimeout(() => inputRef.current?.focus(), 50);
                }
        }, [open]);

        useEffect(() => {
                setSelectedIndex(0);
        }, []);

        const execute = (result: PaletteItem) => {
                if (result.type === "command") {
                        if (result.item.path) {
                                navigate(result.item.path);
                        }
                }
                setQuery("");
                onOpenChange(false);
        };

        const handleKeyDown = (e: React.KeyboardEvent) => {
                if (e.key === "ArrowDown") {
                        e.preventDefault();
                        setSelectedIndex((prev) => (prev + 1) % results.length);
                } else if (e.key === "ArrowUp") {
                        e.preventDefault();
                        setSelectedIndex((prev) => (prev - 1 + results.length) % results.length);
                } else if (e.key === "Enter") {
                        e.preventDefault();
                        execute(results[selectedIndex]);
                } else if (e.key === "Escape") {
                        e.preventDefault();
                        setQuery("");
                        onOpenChange(false);
                }
        };

        useEffect(() => {
                if (selectedIndex >= results.length && results.length > 0) {
                        setSelectedIndex(results.length - 1);
                }
        }, [selectedIndex, results.length]);

        useEffect(() => {
                if (!open || !listRef.current) {
                        return;
                }
                const items = listRef.current.querySelectorAll('[role="option"]');
                const active = items[selectedIndex];
                if (active) {
                        active.scrollIntoView({ block: "nearest" });
                }
        }, [selectedIndex, open]);

        if (!open) {
                return null;
        }

        return (
                <div className="fixed inset-0 z-[200] flex items-start justify-center pt-[20vh]">
                        <div  // NOSONAR: typescript:S6819
                                className="absolute inset-0 bg-black/70"
                                role="button"
                                tabIndex={0}
                                aria-label="Close command palette"
                                onClick={() => onOpenChange(false)}
                                onKeyDown={(e) => {
                                        if (e.key === "Enter" || e.key === " ") {
                                                e.preventDefault();
                                                onOpenChange(false);
                                        }
                                }}
                        />
                        <div className="relative w-full max-w-xl mx-4 bg-card border border-border rounded-md shadow-2xl overflow-hidden">
                                <div className="flex items-center gap-3 p-4 border-b border-border">
                                        <Search aria-hidden="true" className="h-5 w-5 text-muted-foreground shrink-0" />
                                        <input
                                                ref={inputRef}
                                                type="text"
                                                value={query}
                                                onChange={(e) => setQuery(e.target.value)}
                                                onKeyDown={handleKeyDown}
                                                placeholder="Type a command or search help..."
                                                className="flex-1 bg-transparent text-foreground text-sm placeholder:text-muted-foreground outline-none"
                                        />
                                        <button
                                                type="button"
                                                onClick={() => onOpenChange(false)}
                                                className="text-xs text-muted-foreground border border-border rounded px-2 py-1 hover:text-foreground/90"
                                                aria-label="Close command palette"
                                        >
                                                ESC
                                        </button>
                                </div>

                                <div ref={listRef} className="max-h-80 overflow-y-auto p-2">
                                        {results.length === 0 ? (
                                                <div className="py-6 text-center text-sm text-muted-foreground">
                                                        No results found
                                                </div>
                                        ) : (
                                                results.map((result, index) => {
                                                        const isActive = index === selectedIndex;
                                                        if (result.type === "command") {
                                                                return (
                                                                        <button  // NOSONAR: typescript:S6819
                                                                                key={result.item.id}
                                                                                role="option"
                                                                                aria-selected={isActive}
                                                                                onClick={() => execute(result)} onKeyDown={(e) => { if (e.key === "Enter") (() => execute(result))(); }}                                                                          onMouseEnter={() => setSelectedIndex(index)}
                                                                                className={cn(
                                                                                        "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors",
                                                                                        isActive
                                                                                                ? "bg-card text-foreground"
                                                                                                : "text-foreground/90 hover:bg-card/60",
                                                                                )}
                                                                        >
                                                                                <span className="flex h-8 w-8 items-center justify-center rounded bg-card text-muted-foreground">
                                                                                        {result.item.icon || <Search aria-hidden="true" className="h-4 w-4" />}
                                                                                </span>
                                                                                <span className="flex-1 text-left">
                                                                                        {result.item.label}
                                                                                </span>
                                                                                {result.item.shortcut && (
                                                                                        <span className="flex gap-1">
                                                                                                <kbd className="hidden sm:inline-block rounded bg-card border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground">
                                                                                                        {result.item.shortcut}
                                                                                                </kbd>
                                                                                        </span>
                                                                                )}
                                                                        </button>
                                                                );
                                                        }

                                                        const title = result.item.titleEn;
                                                        return (
                                                                <button  // NOSONAR: typescript:S6819
                                                                        key={result.item.id}
                                                                        role="option"
                                                                        aria-selected={isActive}
                                                                        onClick={() => execute(result)} onKeyDown={(e) => { if (e.key === "Enter") (() => execute(result))(); }}                                                                  onMouseEnter={() => setSelectedIndex(index)}
                                                                        className={cn(
                                                                                "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors",
                                                                                isActive
                                                                                        ? "bg-card text-foreground"
                                                                                        : "text-foreground/90 hover:bg-card/60",
                                                                        )}
                                                                >
                                                                        <span className="flex h-8 w-8 items-center justify-center rounded bg-card text-muted-foreground">
                                                                                <Search aria-hidden="true" className="h-4 w-4" />
                                                                        </span>
                                                                        <span className="flex-1 text-left">
                                                                                <span className="block text-foreground">{title}</span>
                                                                                <span className="block text-xs text-muted-foreground">
                                                                                        {result.item.id}
                                                                                </span>
                                                                        </span>
                                                                        <span className="text-[10px] text-muted-foreground border border-border rounded px-1.5 py-0.5">
                                                                                HELP
                                                                        </span>
                                                                </button>
                                                        );
                                                })
                                        )}
                                </div>

                                <div className="flex items-center justify-between border-t border-border px-4 py-2 text-xs text-muted-foreground">
                                        <span>{results.length} results</span>
                                        <div className="flex items-center gap-3">
                                                <span className="flex items-center gap-1">
                                                        <kbd className="rounded bg-card border border-border px-1 py-0.5 text-[10px]">
                                                                ↑↓
                                                        </kbd>{" "}
                                                        navigate
                                                </span>
                                                <span className="flex items-center gap-1">
                                                        <kbd className="rounded bg-card border border-border px-1 py-0.5 text-[10px]">
                                                                ↵
                                                        </kbd>{" "}
                                                        select
                                                </span>
                                        </div>
                                </div>
                        </div>
                </div>
        );
};

export default CommandPalette;
