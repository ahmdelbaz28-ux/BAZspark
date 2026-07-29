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
import { LoginModal } from "@/components/auth/LoginModal";
import { LoginSuccess } from "@/components/auth/LoginSuccess";

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

const features = [
  { icon: Compass, cls: "icon-box-cad", title: "feature1Title", desc: "feature1Desc" },
  { icon: ShieldCheck, cls: "icon-box-compliance", title: "feature2Title", desc: "feature2Desc" },
  { icon: Layers, cls: "icon-box-bim", title: "feature3Title", desc: "feature3Desc" },
  { icon: Bot, cls: "icon-box-ai", title: "feature4Title", desc: "feature4Desc" },
  { icon: Anchor, cls: "icon-box-marine", title: "feature5Title", desc: "feature5Desc" },
] as const;

export function VariantA(props: LoginVariantProps) {
  const { lang, t, apiKey, setApiKey, showKey, setShowKey, remember, setRemember, submitting, error, isSuccess, showSupportModal, setShowSupportModal, showRequestModal, setShowRequestModal, handleSubmit, handleAutoFillTestKey, toggleLanguage } = props;

  return (
    <div className={`login-screen-root ${lang === "ar" ? "rtl" : "ltr"}`} dir={lang === "ar" ? "rtl" : "ltr"} role="main" aria-label="BAZSPARK Login">
      <div className="login-noise-overlay" aria-hidden="true" />

      <header className="login-header-lang">
        <button type="button" onClick={toggleLanguage} className="lang-toggle-btn" aria-label="Switch Language">
          <Globe aria-hidden="true" className="size-3.5 text-cyan-400" />
          <span className={`text-[11px] font-mono font-bold tracking-wider ${lang === "en" ? "text-cyan-400" : "text-slate-400"}`}>EN</span>
          <span className="text-slate-600">|</span>
          <span className={`text-[11px] font-mono font-bold tracking-wider ${lang === "ar" ? "text-cyan-400" : "text-slate-400"}`}>العربية</span>
        </button>
      </header>

      <div className="login-split-container">
        <div className="login-left-panel">
          <div className="w-full max-w-[580px] my-auto">
            <div className="login-logo-card login-entrance-1">
              <BazSparkLogo size={42} animated />
              <div className="flex flex-col">
                <BazSparkWordmark size="md" />
                <span className="text-[0.6rem] font-mono font-extrabold tracking-[0.15em] text-slate-500 uppercase mt-0.5">
                  {t.topBadge}
                </span>
              </div>
            </div>
            <h1 className="login-hero-title login-entrance-2">{t.heroTitle}</h1>
            <p className="login-hero-subtitle login-entrance-3">{t.heroSubtitle}</p>
            <div className="login-feature-list">
              {features.map((f, i) => (
                <motion.div
                  key={f.cls}
                  className="login-feature-item"
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.4 + i * 0.08, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                >
                  <div className={`feature-icon-box ${f.cls}`}>
                    <f.icon className="size-5" />
                  </div>
                  <div>
                    <div className="login-feature-title">{t[f.title]}</div>
                    <div className="login-feature-desc">{t[f.desc]}</div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>

        <div className="login-right-panel">
          <div className="login-form-wrapper">
            <h2 className="login-form-title">{t.formTitle}</h2>
            <p className="login-form-subtitle">{t.formSubtitle}</p>
            <div className="min-h-[300px] relative">
              <AnimatePresence mode="wait">
                {!isSuccess ? (
                  <motion.div key="form-view" initial={{ opacity: 1 }} exit={{ opacity: 0, y: -12 }}>
                    <form onSubmit={handleSubmit}>
                      {error && (
                        <div className="flex gap-3 bg-rose-500/10 border border-rose-500/25 text-rose-400 p-3.5 rounded-lg text-xs mb-5" role="alert">
                          <AlertCircle aria-hidden="true" className="size-4 text-rose-400 shrink-0 mt-0.5" />
                          <div>
                            <div className="font-extrabold uppercase tracking-widest text-[0.6rem]">
                              {lang === "ar" ? "فشل تسجيل الدخول" : "Sign-in failed"}
                            </div>
                            <div className="opacity-90 mt-0.5">{error}</div>
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
                          {showKey ? <EyeOff aria-hidden="true" className="size-4" /> : <Eye aria-hidden="true" className="size-4" />}
                        </button>
                      </div>
                      <div className="input-sub-row">
                        <span className="truncate pr-2">{t.inputHint}</span>
                        <button type="button" onClick={() => setShowRequestModal(true)} className="support-link-btn shrink-0">{t.requestAccessLink}</button>
                      </div>
                      <div className="remember-checkbox-row">
                        <Checkbox id="remember" checked={remember} onCheckedChange={(v) => setRemember(v === true)} disabled={submitting} className="border-slate-800 h-4 w-4 data-[state=checked]:bg-rose-500 data-[state=checked]:border-rose-500" />
                        <Label htmlFor="remember" className="text-[0.775rem] cursor-pointer text-slate-400 select-none">{t.rememberLabel}</Label>
                      </div>
                      <button type="submit" className="login-submit-btn" disabled={submitting || !apiKey.trim()}>
                        {submitting ? (
                          <><Loader2 aria-hidden="true" className="size-4 animate-spin" />{t.submittingButton}</>
                        ) : (
                          <><ShieldCheck aria-hidden="true" className="size-4" />{t.submitButton}</>
                        )}
                      </button>
                    </form>
                  </motion.div>
                ) : (
                  <LoginSuccess
                    accessGranted={t.accessGranted}
                    sessionInitialized={t.sessionInitialized}
                    redirecting={t.redirecting}
                  />
                )}
              </AnimatePresence>
            </div>
          </div>
          <footer className="login-footer-bar">
            <div className="footer-encryption-status"><Lock className="size-3" /><span>{t.footerEncryption}</span></div>
            <div>{t.footerVersion}</div>
          </footer>
        </div>
      </div>

      <LoginModal
        open={showSupportModal}
        onClose={() => setShowSupportModal(false)}
        title={t.supportTitle}
        icon={<HelpCircle className="size-5 text-cyan-400" />}
      >
        <p className="text-[0.775rem] text-slate-300 leading-relaxed mb-4">{t.supportDesc}</p>
        <div className="text-xs font-mono bg-[#050811] p-3 rounded-lg border border-slate-800 text-slate-400 mb-5">
          <div>{t.supportEmail}</div>
          <div className="mt-1">Standard Format: BS-XXXX-XXXX-XXXX-XXXX</div>
        </div>
        <div className="flex justify-end">
          <Button type="button" onClick={() => setShowSupportModal(false)} className="bg-slate-800 hover:bg-slate-700 text-white text-xs px-4 h-9">{t.closeBtn}</Button>
        </div>
      </LoginModal>

      <LoginModal
        open={showRequestModal}
        onClose={() => setShowRequestModal(false)}
        title={t.requestTitle}
        icon={<Sparkles className="size-5 text-red-400" />}
      >
        <p className="text-[0.775rem] text-slate-300 leading-relaxed mb-5">{t.requestDesc}</p>
        <Button type="button" onClick={handleAutoFillTestKey} className="w-full bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs h-10 tracking-wider flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20 mb-4">
          <Sparkles className="size-4" />
          {t.autoFillDemoBtn}
        </Button>
        <div className="flex justify-end">
          <Button type="button" onClick={() => setShowRequestModal(false)} className="bg-slate-800 hover:bg-slate-700 text-white text-xs px-4 h-9">{t.closeBtn}</Button>
        </div>
      </LoginModal>
    </div>
  );
}
