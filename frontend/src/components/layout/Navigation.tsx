import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { SunIcon, MoonIcon } from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";

const Navigation: React.FC = () => {
  const { dark, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const links = [
    { to: "/", label: "Dashboard" },
    { to: "/projects", label: "Projects" },
    { to: "/engineering", label: "Engineering" },
    { to: "/fire-alarm-designer", label: "Fire Alarm Designer" },
    { to: "/digital-twin", label: "Digital Twin" },
    { to: "/settings", label: "Settings" },
  ];

  return (
    <div className="relative" ref={menuRef}>
      <button
        className={`
          px-3 py-2 text-base font-medium text-muted-foreground
          hover:text-cyan-300 hover:bg-white/5 dark:hover:bg-gray-800
          rounded-md transition-colors
        `}
        onClick={() => setOpen(!open)}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label="Navigation menu"
      >
        ☰
      </button>

      {open && (
        <div className="absolute left-0 top-full mt-1 z-50 min-w-[200px] bg-background border border-white/10 rounded-lg shadow-xl overflow-hidden">
          <div className="py-1">
            {links.map(({ to, label }) => (
              <Link
                key={to}
                to={to}
                className={`
                  block py-2 px-4 text-sm text-muted-foreground
                  hover:bg-white/5 dark:hover:bg-gray-800
                  transition-colors
                  hover:text-cyan-300 dark:hover:text-cyan-300
                `}
                onClick={() => setOpen(false)}
              >
                {label}
              </Link>
            ))}
          </div>

          <div className="border-t border-white/10 px-4 py-2 flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              Dark mode
            </span>
            <button
              onClick={toggle}
              className="rounded bg-gray-200 dark:bg-gray-700 px-2 py-1 text-xs transition-colors"
              aria-label="Toggle dark mode"
            >
              {dark ? (
                <MoonIcon className="w-4 h-4" />
              ) : (
                <SunIcon className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Navigation;