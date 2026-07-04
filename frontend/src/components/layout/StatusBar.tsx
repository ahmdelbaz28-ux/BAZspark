import React from "react";

interface StatusBarProps {
  backendUrl: string;
  isConnected: boolean;
  environment: string;
}

const StatusBar: React.FC<StatusBarProps> = ({
  backendUrl,
  isConnected,
  environment,
}) => {
  return (
    <footer
      data-onboarding="status-bar"
      className="
        h-6 shrink-0 flex items-center px-3 gap-3
        bg-[#0a0a0e] border-t border-[#131318]
        text-[10px] font-mono text-[#3a3a50]
        select-none
      "
    >
      {/* Brand + version */}
      <span className="text-[#2e2e42] tracking-wider uppercase">BAZSPARK</span>
      <span className="text-[#1e1e2a]">v55.0.0</span>

      <span className="text-[#1a1a22]">·</span>

      {/* Backend URL */}
      <span className="truncate max-w-[180px] text-[#2a2a3a]" title={backendUrl}>
        {backendUrl}
      </span>

      <span className="text-[#1a1a22]">·</span>

      {/* Environment */}
      <span className="uppercase tracking-wider text-[#2a2a3a]">{environment}</span>

      <div className="flex-1" />

      {/* NFPA badge */}
      <span className="text-[#2a2a42] tracking-wider">NFPA&nbsp;72</span>

      <span className="text-[#1a1a22]">·</span>

      {/* Connection */}
      <div className="flex items-center gap-1.5">
        <span className={`baz-dot ${isConnected ? "baz-dot-online" : "baz-dot-offline"}`} />
        <span className={isConnected ? "text-[#3a5a3a]" : "text-[#5a3a3a]"}>
          {isConnected ? "connected" : "offline"}
        </span>
      </div>
    </footer>
  );
};

export default StatusBar;
