import {
	AlertCircle, Eye, EyeOff, Globe, KeyRound,
	Loader2, ShieldCheck, Sparkles, X,
} from "lucide-react";
import { type FormEvent } from "react";
import { BazSparkLogo, BazSparkWordmark } from "@/components/auth/BazSparkLogo";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";

interface LoginVariantProps {
  lang: "en" | "ar";
  t: Record<string, string>;
  apiKey: string;
  setApiKey: (v: string) => void;
  showKey: boolean;
  setShowKey: (v: boolean) => void;
  remember: boolean;
  setRemember: (v: boolean) => void;
  submitting: boolean;
  error: string | null;
  isSuccess: boolean;
  showSupportModal: boolean;
  setShowSupportModal: (v: boolean) => void;
  showRequestModal: boolean;
  setShowRequestModal: (v: boolean) => void;
  handleSubmit: (e: FormEvent) => Promise<void>;
  handleAutoFillTestKey: () => void;
  toggleLanguage: () => void;
}

export function VariantB(props: LoginVariantProps) {
  const { lang, t, apiKey, setApiKey, showKey, setShowKey, submitting, error, isSuccess, showSupportModal, setShowSupportModal, showRequestModal, setShowRequestModal, handleSubmit, handleAutoFillTestKey, toggleLanguage } = props;

  return (
    <div dir={lang === "ar" ? "rtl" : "ltr"} style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", backgroundColor: "#070b16", padding: "1rem", position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(56,189,248,0.06), transparent)" }} />

      <div style={{ position: "absolute", top: "1.5rem", right: "2rem", zIndex: 10 }}>
        <button onClick={toggleLanguage} style={{ display: "flex", alignItems: "center", gap: "0.4rem", background: "rgba(12,17,32,0.8)", border: "1px solid rgba(30,41,59,0.9)", borderRadius: "0.5rem", padding: "0.3rem 0.65rem", fontFamily: "monospace", fontSize: "0.7rem", fontWeight: 700, color: "#cbd5e1", cursor: "pointer" }}>
          <Globe style={{ width: "0.8rem", height: "0.8rem", color: "#38bdf8" }} />
          {lang === "en" ? "AR" : "EN"}
        </button>
      </div>

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} style={{ width: "100%", maxWidth: "420px" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", marginBottom: "2rem" }}>
          <div style={{ marginBottom: "1rem" }}>
            <BazSparkLogo size={48} animated />
          </div>
          <BazSparkWordmark size="lg" />
          <p style={{ fontSize: "0.8rem", color: "#64748b", marginTop: "0.5rem", fontFamily: "monospace", letterSpacing: "0.1em" }}>
            {t.topBadge}
          </p>
        </div>

        <div style={{ backgroundColor: "rgba(10,14,26,0.8)", border: "1px solid rgba(30,41,59,0.7)", borderRadius: "1rem", padding: "2rem", backdropFilter: "blur(12px)" }}>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#ffffff", marginBottom: "0.3rem" }}>{t.formTitle}</h2>
          <p style={{ fontSize: "0.8rem", color: "#94a3b8", marginBottom: "1.5rem" }}>{t.formSubtitle}</p>

          <AnimatePresence mode="wait">
            {!isSuccess ? (
              <motion.div key="form-view" initial={{ opacity: 1 }} exit={{ opacity: 0, y: -12 }}>
                <form onSubmit={handleSubmit}>
                  {error && (
                    <div style={{ display: "flex", gap: "0.6rem", alignItems: "flex-start", backgroundColor: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185", padding: "0.75rem", borderRadius: "0.5rem", fontSize: "0.7rem", marginBottom: "1rem" }} role="alert">
                      <AlertCircle style={{ width: "0.85rem", height: "0.85rem", flexShrink: 0, marginTop: "0.05rem" }} />
                      <div>
                        <div style={{ fontWeight: 700, fontSize: "0.6rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>{lang === "ar" ? "خطأ" : "Error"}</div>
                        <div style={{ marginTop: "0.1rem" }}>{error}</div>
                      </div>
                    </div>
                  )}

                  <label style={{ display: "block", fontSize: "0.65rem", fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "0.4rem" }}>{t.inputLabel}</label>
                  <div style={{ position: "relative", marginBottom: "0.3rem" }}>
                    <KeyRound style={{ position: "absolute", left: "0.85rem", top: "50%", transform: "translateY(-50%)", width: "0.9rem", height: "0.9rem", color: "#64748b", pointerEvents: "none" }} />
                    <input
                      type={showKey ? "text" : "password"}
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder={t.inputPlaceholder}
                      disabled={submitting}
                      autoFocus
                      style={{ width: "100%", height: "2.75rem", paddingLeft: "2.5rem", paddingRight: "2.5rem", backgroundColor: "#050811", border: "1px solid #1e293b", borderRadius: "0.5rem", color: "#ffffff", fontFamily: "monospace", fontSize: "0.8rem", boxSizing: "border-box", transition: "border-color 0.2s" }}
                      onFocus={(e) => { e.target.style.borderColor = "#38bdf8"; e.target.style.outline = "none"; }}
                      onBlur={(e) => { e.target.style.borderColor = "#1e293b"; }}
                    />
                    <button type="button" onClick={() => setShowKey(!showKey)} style={{ position: "absolute", right: "0.85rem", top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: "#64748b", cursor: "pointer", padding: "0.2rem", display: "flex" }}>
                      {showKey ? <EyeOff style={{ width: "0.9rem", height: "0.9rem" }} /> : <Eye style={{ width: "0.9rem", height: "0.9rem" }} />}
                    </button>
                  </div>
                  <p style={{ fontSize: "0.65rem", color: "#475569", marginBottom: "0.25rem" }}>{t.inputHint}</p>

                  <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem", marginBottom: "1.25rem" }}>
                    <button type="button" onClick={() => setShowSupportModal(true)} style={{ flex: 1, background: "none", border: "1px solid #1e293b", borderRadius: "0.5rem", padding: "0.4rem", fontSize: "0.65rem", fontWeight: 600, color: "#38bdf8", cursor: "pointer" }}>{t.supportLink}</button>
                    <button type="button" onClick={() => setShowRequestModal(true)} style={{ flex: 1, background: "none", border: "1px solid #1e293b", borderRadius: "0.5rem", padding: "0.4rem", fontSize: "0.65rem", fontWeight: 600, color: "#f87171", cursor: "pointer" }}>{t.requestAccessLink}</button>
                  </div>

                  <button type="submit" disabled={submitting || !apiKey.trim()} style={{ width: "100%", height: "2.75rem", backgroundColor: "#2563eb", border: "none", borderRadius: "0.5rem", color: "#ffffff", fontWeight: 700, fontSize: "0.8rem", cursor: submitting ? "not-allowed" : "pointer", opacity: submitting ? 0.6 : 1, display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem", transition: "background-color 0.2s", boxShadow: "0 8px 16px rgba(37,99,235,0.25)" }}>
                    {submitting ? <><Loader2 className="animate-spin" style={{ width: "1rem", height: "1rem" }} />{t.submittingButton}</> : <><ShieldCheck style={{ width: "1rem", height: "1rem" }} />{t.submitButton}</>}
                  </button>
                </form>
              </motion.div>
            ) : (
              <motion.div key="success-view" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} style={{ textAlign: "center", padding: "2rem 1rem" }}>
                <div style={{ width: "3.5rem", height: "3.5rem", borderRadius: "9999px", backgroundColor: "rgba(6,78,59,0.8)", border: "1px solid rgba(52,211,153,0.3)", display: "flex", alignItems: "center", justifyContent: "center", color: "#34d399", margin: "0 auto 1rem" }}>
                  <ShieldCheck style={{ width: "1.75rem", height: "1.75rem" }} />
                </div>
                <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "#ffffff" }}>{t.accessGranted}</h3>
                <p style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.25rem" }}>{t.sessionInitialized}</p>
                <span style={{ display: "block", marginTop: "0.75rem", fontSize: "0.6rem", fontFamily: "monospace", letterSpacing: "0.1em", color: "#34d399" }}>{t.redirecting}</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div style={{ textAlign: "center", marginTop: "1.5rem", fontSize: "0.65rem", fontFamily: "monospace", color: "#475569" }}>
          <span style={{ color: "#34d399" }}>AES-256</span> · System v8.1
        </div>
      </motion.div>

      <AnimatePresence>
        {showSupportModal && (
          <div style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem", backgroundColor: "rgba(0,0,0,0.7)", backdropFilter: "blur(6px)" }}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={{ width: "100%", maxWidth: "400px", backgroundColor: "#0a0f1d", border: "1px solid #1e293b", borderRadius: "0.75rem", padding: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff" }}>{t.supportTitle}</h3>
                <button onClick={() => setShowSupportModal(false)} style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer" }}><X style={{ width: "1rem", height: "1rem" }} /></button>
              </div>
              <p style={{ fontSize: "0.75rem", color: "#cbd5e1", marginBottom: "1rem" }}>{t.supportDesc}</p>
              <div style={{ fontSize: "0.7rem", fontFamily: "monospace", backgroundColor: "#050811", padding: "0.75rem", borderRadius: "0.5rem", border: "1px solid #1e293b", color: "#94a3b8", marginBottom: "1rem" }}>{t.supportEmail}</div>
              <Button onClick={() => setShowSupportModal(false)} className="bg-slate-800 hover:bg-slate-700 text-white text-xs px-4 h-9 w-full">{t.closeBtn}</Button>
            </motion.div>
          </div>
        )}
        {showRequestModal && (
          <div style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem", backgroundColor: "rgba(0,0,0,0.7)", backdropFilter: "blur(6px)" }}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={{ width: "100%", maxWidth: "400px", backgroundColor: "#0a0f1d", border: "1px solid #1e293b", borderRadius: "0.75rem", padding: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff" }}>{t.requestTitle}</h3>
                <button onClick={() => setShowRequestModal(false)} style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer" }}><X style={{ width: "1rem", height: "1rem" }} /></button>
              </div>
              <p style={{ fontSize: "0.75rem", color: "#cbd5e1", marginBottom: "1.25rem" }}>{t.requestDesc}</p>
              <Button onClick={handleAutoFillTestKey} className="w-full bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs h-10 flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20 mb-3">
                <Sparkles style={{ width: "1rem", height: "1rem" }} />
                {t.autoFillDemoBtn}
              </Button>
              <Button onClick={() => setShowRequestModal(false)} className="bg-slate-800 hover:bg-slate-700 text-white text-xs px-4 h-9 w-full">{t.closeBtn}</Button>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}