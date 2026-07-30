/**
 * AdvancedSettingsPage.tsx — Environment Configuration Manager.
 *
 * Provides editable UI forms for 15+ env-var-only settings grouped by category:
 * NVIDIA, Langfuse, Akamai, Database, Pipeline, Integrations, CORS.
 *
 * Settings are fetched from GET /api/v1/env-config and saved via PUT /api/v1/env-config.
 * Secret values are masked in the UI and never shown in plaintext.
 */
import React, { useCallback, useEffect, useState } from "react";
import { Settings2, Loader2, RefreshCw, AlertTriangle, CheckCircle2, Save, Eye, EyeOff } from "lucide-react";

// ── Types ───────────────────────────────────────────────────────────────────

interface EnvSetting {
  key: string;
  label: string;
  type: "string" | "secret" | "boolean" | "number" | "url";
  value: string;
  is_set: boolean;
  is_secret: boolean;
  source: "env" | "default" | "override";
}

interface ConfigCategory {
  label: string;
  settings: EnvSetting[];
}

interface EnvConfigData {
  categories: Record<string, ConfigCategory>;
}

interface EnvConfigResponse {
  success: boolean;
  data: EnvConfigData;
}

// ── Category Icons ──────────────────────────────────────────────────────────

const CATEGORY_META: Record<string, { icon: string; description: string }> = {
  nvidia: { icon: "🧠", description: "NVIDIA LLM API configuration for AI-powered engineering" },
  langfuse: { icon: "🔍", description: "Langfuse observability and LLM tracing settings" },
  akamai: { icon: "🛡️", description: "Akamai CDN, edge security, and geoblocking" },
  database: { icon: "🗄️", description: "PostgreSQL, Qdrant, Neo4j, and Redis connections" },
  pipeline: { icon: "⚙️", description: "Backend pipeline performance and processing parameters" },
  integrations: { icon: "🔗", description: "Third-party API keys: Resend, Supabase, GitHub, HF" },
  cors: { icon: "🌐", description: "Cross-Origin Resource Sharing and allowed origins" },
};

// ── Component ───────────────────────────────────────────────────────────────

export const AdvancedSettingsPage: React.FC = () => {
  const [configData, setConfigData] = useState<EnvConfigData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<Record<string, "saving" | "saved" | "error">>({});
  const [activeCategory, setActiveCategory] = useState<string>("nvidia");
  const [visibleSecrets, setVisibleSecrets] = useState<Set<string>>(new Set());
  const [editedValues, setEditedValues] = useState<Record<string, string>>({});

  const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/env-config`, {
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: EnvConfigResponse = await res.json();
      if (data.success && data.data) {
        setConfigData(data.data);
        // Initialize edited values from current config
        const initial: Record<string, string> = {};
        for (const cat of Object.values(data.data.categories)) {
          for (const s of cat.settings) {
            initial[s.key] = s.value;
          }
        }
        setEditedValues(initial);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load configuration");
    } finally {
      setLoading(false);
    }
  }, [API_BASE]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleValueChange = (key: string, value: string) => {
    setEditedValues((prev) => ({ ...prev, [key]: value }));
  };

  const toggleSecretVisibility = (key: string) => {
    setVisibleSecrets((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const handleSaveCategory = async (categoryKey: string) => {
    if (!configData) return;
    setSaving(categoryKey);      setSaveStatus((prev) => ({ ...prev, [categoryKey]: "saving" as const }));

    // Gather only the settings for this category that have been changed
    const overrides: Record<string, string> = {};
    const settings = configData.categories[categoryKey].settings;
    for (const s of settings) {
      const edited = editedValues[s.key];
      const original = s.value;
      // Only include if value differs from original (and for secrets, always include the visible edit)
      if (edited !== original || visibleSecrets.has(s.key)) {
        overrides[s.key] = edited;
      }
    }

    if (Object.keys(overrides).length === 0) {        setSaveStatus((prev) => ({ ...prev, [categoryKey]: "saved" as const }));
      setTimeout(() => setSaveStatus((prev) => { const next = { ...prev }; delete next[categoryKey]; return next; }), 2000);
      setSaving(null);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/env-config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ overrides }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.success) {
        setSaveStatus((prev) => ({ ...prev, [categoryKey]: "saved" as const }));
        // Refresh config to get updated masked values
        await fetchConfig();
      } else {
        throw new Error(data.message || "Save failed");
      }
    } catch (err) {        setSaveStatus((prev) => ({ ...prev, [categoryKey]: "error" as const }));
      } finally {
        setTimeout(() => setSaveStatus((prev) => { const next = { ...prev }; delete next[categoryKey]; return next; }), 3000);
      setSaving(null);
    }
  };

  const renderSettingInput = (setting: EnvSetting) => {
    const isVisible = visibleSecrets.has(setting.key);
    const value = editedValues[setting.key] ?? setting.value;

    if (setting.type === "boolean") {
      const isChecked = value === "true" || value === "1";
      return (
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            className="sr-only peer"
            checked={isChecked}
            onChange={(e) => handleValueChange(setting.key, e.target.checked ? "true" : "false")}
          />
          <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600" />
        </label>
      );
    }

    if (setting.is_secret || setting.type === "secret") {
      const displayValue = isVisible ? value : setting.value;
      return (
        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              type={isVisible ? "text" : "password"}
              value={value}
              onChange={(e) => handleValueChange(setting.key, e.target.value)}
              placeholder={setting.is_set ? "••••••••" : `Default: ${setting.type === "url" ? "https://..." : "Not set"}`}
              className="w-full px-3 py-2 pr-9 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono placeholder-slate-600 focus:border-blue-500 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => toggleSecretVisibility(setting.key)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
              title={isVisible ? "Hide value" : "Show value"}
            >
              {isVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>
      );
    }

    if (setting.type === "number") {
      return (
        <input
          type="number"
          value={value}
          onChange={(e) => handleValueChange(setting.key, e.target.value)}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-blue-500 focus:outline-none"
        />
      );
    }

    return (
      <input
        type="text"
        value={value}
        onChange={(e) => handleValueChange(setting.key, e.target.value)}
        placeholder={`Default: ${setting.type === "url" ? "https://..." : "Not set"}`}
        className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-blue-500 focus:outline-none"
      />
    );
  };

  const getSourceBadge = (source: string) => {
    switch (source) {
      case "env":
        return <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-green-500/15 text-green-400 border border-green-500/30">Env</span>;
      case "override":
        return <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400 border border-blue-500/30">Override</span>;
      default:
        return <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-500/15 text-slate-400 border border-slate-500/30">Default</span>;
    }
  };

  const categoryKeys = configData ? Object.keys(configData.categories) : [];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-100 flex items-center gap-2">
            <Settings2 className="h-8 w-8 text-purple-500" />
            Environment Configuration
          </h1>
          <p className="text-slate-400 mt-2">
            Manage all environment-level settings — changes persist in the database and apply on next server restart
          </p>
        </div>
        <button
          type="button"
          onClick={fetchConfig}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg text-sm transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 text-purple-400 animate-spin" />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-red-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-400">Failed to load configuration</p>
            <p className="text-xs text-red-300/70 mt-1">{error}</p>
          </div>
        </div>
      )}

      {/* Main Content */}
      {!loading && configData && (
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Sidebar Category Nav */}
          <div className="lg:w-56 shrink-0">
            <nav className="space-y-1 sticky top-6">
              {categoryKeys.map((key) => {
                const meta = CATEGORY_META[key];
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setActiveCategory(key)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-all text-left ${
                      activeCategory === key
                        ? "bg-purple-500/15 text-purple-300 border border-purple-500/30"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent"
                    }`}
                  >
                    <span className="text-base">{meta?.icon || "⚙️"}</span>
                    <span>{configData.categories[key]?.label || key}</span>
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Settings Forms */}
          <div className="flex-1 min-w-0">
            {categoryKeys.map((catKey) => {
              if (catKey !== activeCategory) return null;
              const cat = configData.categories[catKey];
              const meta = CATEGORY_META[catKey];
              const status = saveStatus[catKey];

              return (
                <div key={catKey} className="space-y-4">
                  {/* Category Header */}
                  <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xl">{meta?.icon || "⚙️"}</span>
                      <h2 className="text-lg font-semibold text-slate-100">{cat.label}</h2>
                    </div>
                    <p className="text-sm text-slate-400">{meta?.description || ""}</p>
                  </div>

                  {/* Settings */}
                  <div className="bg-slate-800/50 border border-slate-700 rounded-lg divide-y divide-slate-700/50">
                    {cat.settings.map((setting) => (
                      <div key={setting.key} className="p-4 hover:bg-slate-700/20 transition-colors">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <label className="text-sm font-medium text-slate-200">{setting.label}</label>
                              {getSourceBadge(setting.source)}
                            </div>
                            <p className="text-xs text-slate-500 font-mono mb-2">{setting.key}</p>
                          </div>
                          <div className="w-full max-w-sm shrink-0">
                            {renderSettingInput(setting)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Action Bar */}
                  <div className="flex items-center justify-between bg-slate-800/50 border border-slate-700 rounded-lg p-3">
                    <div>
                      {status === "saving" && <span className="text-xs text-blue-400 flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" /> Saving...</span>}
                      {status === "saved" && <span className="text-xs text-green-400 flex items-center gap-1"><CheckCircle2 className="h-3 w-3" /> Saved successfully</span>}
                      {status === "error" && <span className="text-xs text-red-400 flex items-center gap-1"><AlertTriangle className="h-3 w-3" /> Save failed</span>}
                      {!status && <span className="text-xs text-slate-500">Changes persist to the database and apply on next restart</span>}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleSaveCategory(catKey)}
                      disabled={saving === catKey}
                      className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
                    >
                      <Save className="h-4 w-4" />
                      Save {cat.label}
                    </button>
                  </div>

                  {/* Info Note */}
                  <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
                    <p className="text-xs text-amber-400">
                      Some settings require a server restart to take effect. Secrets are encrypted at rest and masked in the UI.
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdvancedSettingsPage;
