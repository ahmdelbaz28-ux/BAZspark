import {
  AlertCircle, Anchor, Bot, Compass, Eye, EyeOff, Globe, HelpCircle,
  KeyRound, Layers, Loader2, Lock, ShieldCheck, Sparkles, X,
} from "lucide-react";
import { type FormEvent } from "react";
import { BazSparkLogo, BazSparkWordmark } from "@/components/auth/BazSparkLogo";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
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

export function VariantA(props: LoginVariantProps) {
  const { lang, t, apiKey, setApiKey, showKey, setShowKey, remember, setRemember, submitting, error, isSuccess, showSupportModal, setShowSupportModal, showRequestModal, setShowRequestModal, handleSubmit, handleAutoFillTestKey, toggleLanguage } = props;

  return (
    <div className={`login-screen-root ${lang === "ar" ? "rtl" : "ltr"}`} dir={lang === "ar" ? "rtl" : "ltr"} role="main" aria-label="BAZSPARK Login">
      <header className="login-header-lang">
        <button type="button" onClick={toggleLanguage} className="lang-toggle-btn" aria-label="Switch Language">
          <Globe aria-hidden="true" style={{ width: "0.9rem", height: "0.9rem", color: "#38bdf8" }} />
          <span style={{ color: lang === "en" ? "#38bdf8" : "#94a3b8" }}>EN</span>
          <span style={{ color: "#475569" }}>|</span>
          <span style={{ color: lang === "ar" ? "#38bdf8" : "#94a3b8" }}>العربية</span>
        </button>
      </header>

      <div className="login-split-container">
        <div className="login-left-panel">
          <div style={{ width: "100%", maxWidth: "580px", margin: "auto 0" }}>
            <div className="login-logo-card">
              <BazSparkLogo size={42} animated />
              <div style={{ display: "flex", flexDirection: "column" }}>
                <BazSparkWordmark size="md" />
                <span style={{ fontSize: "0.6rem", fontFamily: "monospace", fontWeight: 800, letterSpacing: "0.15em", color: "#64748b", textTransform: "uppercase", marginTop: "0.15rem" }}>
                  {t.topBadge}
                </span>
              </div>
            </div>
            <h1 className="login-hero-title">{t.heroTitle}</h1>
            <p className="login-hero-subtitle">{t.heroSubtitle}</p>
            <div className="login-feature-list">
              {[
                { icon: <Compass style={{ width: "1.25rem", height: "1.25rem" }} />, cls: "icon-box-cad", title: t.feature1Title, desc: t.feature1Desc },
                { icon: <ShieldCheck style={{ width: "1.25rem", height: "1.25rem" }} />, cls: "icon-box-compliance", title: t.feature2Title, desc: t.feature2Desc },
                { icon: <Layers style={{ width: "1.25rem", height: "1.25rem" }} />, cls: "icon-box-bim", title: t.feature3Title, desc: t.feature3Desc },
                { icon: <Bot style={{ width: "1.25rem", height: "1.25rem" }} />, cls: "icon-box-ai", title: t.feature4Title, desc: t.feature4Desc },
                { icon: <Anchor style={{ width: "1.25rem", height: "1.25rem" }} />, cls: "icon-box-marine", title: t.feature5Title, desc: t.feature5Desc },
              ].map((f, i) => (
                <div key={i} className="login-feature-item">
                  <div className={`feature-icon-box ${f.cls}`}>{f.icon}</div>
                  <div>
                    <div className="login-feature-title">{f.title}</div>
                    <div className="login-feature-desc">{f.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="login-right-panel">
          <div className="login-form-wrapper">
            <h2 className="login-form-title">{t.formTitle}</h2>
            <p className="login-form-subtitle">{t.formSubtitle}</p>
            <div style={{ minHeight: "300px", position: "relative" }}>
              <AnimatePresence mode="wait">
                {!isSuccess ? (
                  <motion.div key="form-view" initial={{ opacity: 1 }} exit={{ opacity: 0, y: -12 }}>
                    <form onSubmit={handleSubmit}>
                      {error && (
                        <div style={{ display: "flex", gap: "0.75rem", backgroundColor: "rgba(244, 63, 94, 0.1)", border: "1px solid rgba(244, 63, 94, 0.25)", color: "#fb7185", padding: "0.85rem 1rem", borderRadius: "0.5rem", fontSize: "0.75rem", marginBottom: "1.25rem" }} role="alert">
                          <AlertCircle aria-hidden="true" style={{ width: "1rem", height: "1rem", color: "#fb7185", flexShrink: 0, marginTop: "0.1rem" }} />
                          <div>
                            <div style={{ fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em", fontSize: "0.6rem" }}>
                              {lang === "ar" ? "فشل تسجيل الدخول" : "Sign-in failed"}
                            </div>
                            <div style={{ opacity: 0.9, marginTop: "0.1rem" }}>{error}</div>
                          </div>
                        </div>
                      )}
                      <div className="input-label-row">
                        <span>{t.inputLabel}</span>
                        <button type="button" onClick={() => setShowSupportModal(true)} className="support-link-btn">{t.supportLink}</button>
                      </div>
                      <div className="input-field-relative">
                        <KeyRound aria-hidden="true" className="input-icon-left" />
                        <input id="api-key" type={showKey ? "text" : "password"} name="api_key" autoComplete="off" autoFocus placeholder={t.inputPlaceholder} value={apiKey} onChange={(e) => setApiKey(e.target.value)} disabled={submitting} className="login-input-control" />
                        <button type="button" onClick={() => setShowKey(!showKey)} className="input-icon-right" aria-label={showKey ? "Hide API key" : "Show API key"} tabIndex={-1}>
                          {showKey ? <EyeOff aria-hidden="true" style={{ width: "1rem", height: "1rem" }} /> : <Eye aria-hidden="true" style={{ width: "1rem", height: "1rem" }} />}
                        </button>
                      </div>
                      <div className="input-sub-row">
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", paddingRight: "0.5rem" }}>{t.inputHint}</span>
                        <button type="button" onClick={() => setShowRequestModal(true)} className="support-link-btn" style={{ flexShrink: 0 }}>{t.requestAccessLink}</button>
                      </div>
                      <div className="remember-checkbox-row">
                        <Checkbox id="remember" checked={remember} onCheckedChange={(v) => setRemember(v === true)} disabled={submitting} className="border-slate-800 h-4 w-4 data-[state=checked]:bg-rose-500 data-[state=checked]:border-rose-500" />
                        <Label htmlFor="remember" style={{ fontSize: "0.775rem", cursor: "pointer", color: "#94a3b8", userSelect: "none" }}>{t.rememberLabel}</Label>
                      </div>
                      <button type="submit" className="login-submit-btn" disabled={submitting || !apiKey.trim()}>
                        {submitting ? (
                          <><Loader2 aria-hidden="true" className="animate-spin" style={{ width: "1rem", height: "1rem" }} />{t.submittingButton}</>
                        ) : (
                          <><ShieldCheck aria-hidden="true" style={{ width: "1rem", height: "1rem" }} />{t.submitButton}</>
                        )}
                      </button>
                    </form>
                  </motion.div>
                ) : (
                  <motion.div key="success-view" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} style={{ textAlign: "center", padding: "2.5rem 1.5rem", backgroundColor: "rgba(7, 11, 22, 0.9)", border: "1px solid rgba(52, 211, 153, 0.2)", borderRadius: "0.75rem", display: "flex", flexDirection: "column", alignItems: "center", gap: "1rem" }}>
                    <div style={{ width: "4rem", height: "4rem", borderRadius: "9999px", backgroundColor: "rgba(6, 78, 59, 0.8)", border: "1px solid rgba(52, 211, 153, 0.3)", display: "flex", alignItems: "center", color: "#34d399" }}>
                      <ShieldCheck style={{ width: "2rem", height: "2rem", margin: "auto" }} />
                    </div>
                    <div>
                      <h3 style={{ fontSize: "1.125rem", fontWeight: 700, color: "#ffffff" }}>{t.accessGranted}</h3>
                      <p style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.25rem" }}>{t.sessionInitialized}</p>
                    </div>
                    <span style={{ fontSize: "0.6rem", fontFamily: "monospace", letterSpacing: "0.1em", color: "#34d399", textTransform: "uppercase" }}>{t.redirecting}</span>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
          <footer className="login-footer-bar">
            <div className="footer-encryption-status"><Lock style={{ width: "0.75rem", height: "0.75rem" }} /><span>{t.footerEncryption}</span></div>
            <div>{t.footerVersion}</div>
          </footer>
        </div>
      </div>

      <AnimatePresence>
        {showSupportModal && (
          <div style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", padding: "1rem", backgroundColor: "rgba(0, 0, 0, 0.75)", backdropFilter: "blur(4px)" }}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={{ width: "100%", maxWidth: "420px", backgroundColor: "#0a0f1d", border: "1px solid #1e293b", borderRadius: "0.75rem", padding: "1.5rem", boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7)", margin: "auto" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid #1e293b", paddingBottom: "0.75rem", marginBottom: "1rem" }}>
                <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "#ffffff", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <HelpCircle style={{ width: "1.25rem", height: "1.25rem", color: "#38bdf8" }} />
                  {t.supportTitle}
                </h3>
                <button type="button" onClick={() => setShowSupportModal(false)} style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", padding: "0.2rem" }}><X style={{ width: "1rem", height: "1rem" }} /></button>
              </div>
              <p style={{ fontSize: "0.775rem", color: "#cbd5e1", lineHeight: 1.5, marginBottom: "1rem" }}>{t.supportDesc}</p>
              <div style={{ fontSize: "0.75rem", fontFamily: "monospace", backgroundColor: "#050811", padding: "0.75rem", borderRadius: "0.5rem", border: "1px solid #1e293b", color: "#94a3b8", marginBottom: "1.25rem" }}>
                <div>{t.supportEmail}</div>
                <div style={{ marginTop: "0.25rem" }}>Standard Format: BS-XXXX-XXXX-XXXX-XXXX</div>
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <Button type="button" onClick={() => setShowSupportModal(false)} className="bg-slate-800 hover:bg-slate-700 text-white text-xs px-4 h-9">{t.closeBtn}</Button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showRequestModal && (
          <div style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", padding: "1rem", backgroundColor: "rgba(0, 0, 0, 0.75)", backdropFilter: "blur(4px)" }}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} style={{ width: "100%", maxWidth: "420px", backgroundColor: "#0a0f1d", border: "1px solid #1e293b", borderRadius: "0.75rem", padding: "1.5rem", boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7)", margin: "auto" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid #1e293b", paddingBottom: "0.75rem", marginBottom: "1rem" }}>
                <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "#ffffff", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <Sparkles style={{ width: "1.25rem", height: "1.25rem", color: "#f87171" }} />
                  {t.requestTitle}
                </h3>
                <button type="button" onClick={() => setShowRequestModal(false)} style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", padding: "0.2rem" }}><X style={{ width: "1rem", height: "1rem" }} /></button>
              </div>
              <p style={{ fontSize: "0.775rem", color: "#cbd5e1", lineHeight: 1.5, marginBottom: "1.25rem" }}>{t.requestDesc}</p>
              <Button type="button" onClick={handleAutoFillTestKey} className="w-full bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs h-10 tracking-wider flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20 mb-4">
                <Sparkles style={{ width: "1rem", height: "1rem" }} />
                {t.autoFillDemoBtn}
              </Button>
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <Button type="button" onClick={() => setShowRequestModal(false)} className="bg-slate-800 hover:bg-slate-700 text-white text-xs px-4 h-9">{t.closeBtn}</Button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}