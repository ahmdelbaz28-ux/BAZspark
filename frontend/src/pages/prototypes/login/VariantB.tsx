import {
  AlertCircle, Eye, EyeOff, Globe, HelpCircle, KeyRound,
  Loader2, ShieldCheck, Sparkles, X,
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

export function VariantB(props: LoginVariantProps) {
  const { lang, t, apiKey, setApiKey, showKey, setShowKey, remember, setRemember, submitting, error, isSuccess, showSupportModal, setShowSupportModal, showRequestModal, setShowRequestModal, handleSubmit, handleAutoFillTestKey, toggleLanguage } = props;

  return (
    <div dir={lang === "ar" ? "rtl" : "ltr"} className="min-h-screen flex items-center justify-center bg-[#070b16] p-4 relative overflow-hidden">
      <div className="login-noise-overlay" aria-hidden="true" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(56,189,248,0.06),transparent)]" />

      <div className="absolute top-6 right-8 z-10">
        <button onClick={toggleLanguage} className="flex items-center gap-1.5 bg-[#0c1120]/80 border border-slate-800/90 rounded-lg px-2.5 py-1.5 font-mono text-[11px] font-bold text-slate-300 cursor-pointer transition-colors hover:border-cyan-500/30">
          <Globe className="size-3 text-cyan-400" />
          {lang === "en" ? "AR" : "EN"}
        </button>
      </div>

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="w-full max-w-[420px]">
        <div className="flex flex-col items-center text-center mb-8">
          <motion.div initial={{ scale: 0.9 }} animate={{ scale: 1 }} transition={{ delay: 0.15, type: "spring", stiffness: 200 }} className="mb-4">
            <BazSparkLogo size={48} animated />
          </motion.div>
          <BazSparkWordmark size="lg" />
          <p className="text-[0.8rem] text-slate-500 mt-2 font-mono tracking-widest">
            {t.topBadge}
          </p>
        </div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25, duration: 0.5 }} className="login-glass-card rounded-2xl p-8">
          <h2 className="text-xl font-bold text-white mb-1">{t.formTitle}</h2>
          <p className="text-[0.8rem] text-slate-400 mb-6">{t.formSubtitle}</p>

          <AnimatePresence mode="wait">
            {!isSuccess ? (
              <motion.div key="form-view" initial={{ opacity: 1 }} exit={{ opacity: 0, y: -12 }}>
                <form onSubmit={handleSubmit}>
                  {error && (
                    <div className="flex gap-2.5 items-start bg-rose-500/8 border border-rose-500/20 text-rose-400 p-3 rounded-lg text-[11px] mb-4" role="alert">
                      <AlertCircle className="size-3.5 shrink-0 mt-0.5" />
                      <div>
                        <div className="font-bold text-[10px] uppercase tracking-wider">{lang === "ar" ? "خطأ" : "Error"}</div>
                        <div className="mt-0.5">{error}</div>
                      </div>
                    </div>
                  )}

                  <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-1.5">{t.inputLabel}</label>
                  <div className="relative mb-1">
                    <KeyRound className="absolute left-3.5 top-1/2 -translate-y-1/2 size-3.5 text-slate-500 pointer-events-none" />
                    <input
                      type={showKey ? "text" : "password"}
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder={t.inputPlaceholder}
                      disabled={submitting}
                      autoFocus
                      id="api-key"
                      className="login-input-control w-full h-11 pl-10 pr-10 bg-[#050811] border border-slate-800 rounded-lg text-white font-mono text-[0.8rem] box-border"
                    />
                    <button type="button" onClick={() => setShowKey(!showKey)} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 cursor-pointer p-1 bg-transparent border-none flex">
                      {showKey ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
                    </button>
                  </div>
                  <p className="text-[10px] text-slate-600 mb-1">{t.inputHint}</p>

                  <div className="remember-checkbox-row mb-4">
                    <Checkbox id="remember-b" checked={remember} onCheckedChange={(v) => setRemember(v === true)} disabled={submitting} className="border-slate-700 h-4 w-4 data-[state=checked]:bg-rose-500 data-[state=checked]:border-rose-500" />
                    <Label htmlFor="remember-b" className="text-[0.7rem] cursor-pointer text-slate-500 select-none">{t.rememberLabel}</Label>
                  </div>

                  <button type="submit" disabled={submitting || !apiKey.trim()} className="login-submit-btn w-full h-11 bg-blue-600 border-none rounded-lg text-white font-bold text-[0.8rem] cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-blue-600/25">
                    {submitting ? <><Loader2 className="size-4 animate-spin" />{t.submittingButton}</> : <><ShieldCheck className="size-4" />{t.submitButton}</>}
                  </button>

                  <div className="flex gap-2 mt-3">
                    <button type="button" onClick={() => setShowSupportModal(true)} className="flex-1 bg-transparent border border-slate-800 rounded-lg py-1.5 text-[10px] font-semibold text-cyan-400 cursor-pointer transition-colors hover:border-cyan-500/30">{t.supportLink}</button>
                    <button type="button" onClick={() => setShowRequestModal(true)} className="flex-1 bg-transparent border border-slate-800 rounded-lg py-1.5 text-[10px] font-semibold text-red-400 cursor-pointer transition-colors hover:border-red-500/30">{t.requestAccessLink}</button>
                  </div>
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
        </motion.div>

        <div className="text-center mt-6 text-[10px] font-mono text-slate-600">
          <span className="text-emerald-400">AES-256</span> &middot; System v8.1
        </div>
      </motion.div>

      <LoginModal
        open={showSupportModal}
        onClose={() => setShowSupportModal(false)}
        title={t.supportTitle}
        icon={<HelpCircle className="size-5 text-cyan-400" />}
      >
        <p className="text-xs text-slate-300 mb-4">{t.supportDesc}</p>
        <div className="text-[11px] font-mono bg-[#050811] p-3 rounded-lg border border-slate-800 text-slate-400 mb-4">{t.supportEmail}</div>
        <Button onClick={() => setShowSupportModal(false)} className="bg-slate-800 hover:bg-slate-700 text-white text-xs px-4 h-9 w-full">{t.closeBtn}</Button>
      </LoginModal>

      <LoginModal
        open={showRequestModal}
        onClose={() => setShowRequestModal(false)}
        title={t.requestTitle}
        icon={<Sparkles className="size-5 text-cyan-400" />}
      >
        <p className="text-xs text-slate-300 mb-5">{t.requestDesc}</p>
        <Button onClick={handleAutoFillTestKey} className="w-full bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs h-10 flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20 mb-3">
          <Sparkles className="size-4" />
          {t.autoFillDemoBtn}
        </Button>
        <Button onClick={() => setShowRequestModal(false)} className="bg-slate-800 hover:bg-slate-700 text-white text-xs px-4 h-9 w-full">{t.closeBtn}</Button>
      </LoginModal>
    </div>
  );
}
