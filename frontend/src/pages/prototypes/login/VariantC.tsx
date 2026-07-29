import {
  AlertCircle, Eye, EyeOff, Globe, HelpCircle, KeyRound,
  Loader2, ShieldCheck, Sparkles,
} from "lucide-react";
import { useEffect, useRef } from "react";
import { BazSparkLogo } from "@/components/auth/BazSparkLogo";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { motion, AnimatePresence } from "framer-motion";
import { LoginModal } from "@/components/auth/LoginModal";
import { LoginSuccess } from "@/components/auth/LoginSuccess";
import type { LoginVariantProps } from "./types";

function ParticleCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const isBatterySafe = !("getBattery" in navigator);
    if (mq.matches || !isBatterySafe) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let active = true;
    const particles: { x: number; y: number; vx: number; vy: number; r: number; a: number }[] = [];

    const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; };
    resize();
    window.addEventListener("resize", resize);

    for (let i = 0; i < 50; i++) {
      particles.push({
        // NOSONAR — S2245: Math.random() here is for particle animation
        // (visual effect only), not cryptographic purposes.
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        r: Math.random() * 1.5 + 0.5,
        a: Math.random() * 0.4 + 0.1,
      });
    }

    const draw = () => {
      if (!active) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(56, 189, 248, ${p.a})`;
        ctx.fill();
      }
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const distSq = dx * dx + dy * dy;
          if (distSq < 14400) {
            const dist = Math.sqrt(distSq);
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(56, 189, 248, ${0.08 * (1 - dist / 120)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }
      animId = requestAnimationFrame(draw);
    };
    draw();

    const onMotionChange = (e: MediaQueryListEvent) => {
      if (e.matches) { active = false; cancelAnimationFrame(animId); }
    };
    mq.addEventListener("change", onMotionChange);
    return () => { active = false; cancelAnimationFrame(animId); window.removeEventListener("resize", resize); mq.removeEventListener("change", onMotionChange); };
  }, []);

  return <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none" />;
}

export function VariantC(props: LoginVariantProps) {
  const { lang, t, apiKey, setApiKey, showKey, setShowKey, remember, setRemember, submitting, error, isSuccess, showSupportModal, setShowSupportModal, showRequestModal, setShowRequestModal, handleSubmit, handleAutoFillTestKey, toggleLanguage } = props;

  return (
    <div dir={lang === "ar" ? "rtl" : "ltr"} className="min-h-screen flex items-center justify-center bg-[#020409] relative overflow-hidden">
      <div className="login-noise-overlay" aria-hidden="true" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_100%_60%_at_50%_0%,rgba(6,78,112,0.15),transparent),radial-gradient(ellipse_80%_50%_at_50%_100%,rgba(124,58,237,0.08),transparent)]" />
      <ParticleCanvas />

      <div className="absolute top-6 right-8 z-10">
        <button onClick={toggleLanguage} className="flex items-center gap-1.5 bg-white/5 border border-white/10 rounded-full px-3 py-1.5 font-mono text-[10px] font-semibold text-slate-400 cursor-pointer backdrop-blur-md transition-colors hover:bg-white/10">
          <Globe className="size-3 text-cyan-400" />
          {lang === "en" ? "العربية" : "EN"}
        </button>
      </div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1 }} className="w-full max-w-[440px] p-4 relative z-10">
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.6 }} className="text-center mb-8">
          <motion.div initial={{ scale: 0.8 }} animate={{ scale: 1 }} transition={{ delay: 0.4, type: "spring", stiffness: 200 }}>
            <BazSparkLogo size={56} animated />
          </motion.div>
          <h1 className="text-[1.75rem] font-black text-white mt-4 tracking-tight">
            BAZSPARK
          </h1>
          <p className="text-[11px] text-slate-500 font-mono tracking-[0.15em] mt-1 uppercase">
            {t.topBadge}
          </p>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5, duration: 0.6 }}>
          <div className="login-glass-card rounded-2xl p-8 shadow-[0_32px_64px_rgba(0,0,0,0.5)] border-cyan-500/10">
            <AnimatePresence mode="wait">
              {!isSuccess ? (
                <motion.div key="form" initial={{ opacity: 1 }} exit={{ opacity: 0, y: -10 }}>
                  <form onSubmit={handleSubmit}>
                    <div className="flex items-center gap-3 mb-6">
                      <div className="w-1 h-6 rounded-full bg-gradient-to-b from-cyan-400 to-purple-600" />
                      <div>
                        <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">{t.formTitle}</div>
                        <div className="text-[11px] text-slate-400 mt-0.5">{t.formSubtitle}</div>
                      </div>
                    </div>

                    {error && (
                      <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="flex gap-2.5 items-start bg-rose-500/10 border border-rose-500/20 text-rose-400 p-3 rounded-lg text-[11px] mb-4" role="alert">
                        <AlertCircle className="size-3.5 shrink-0 mt-0.5" />
                        <div>
                          <div className="font-bold text-[10px] uppercase tracking-wider">Authentication Error</div>
                          <div className="mt-0.5">{error}</div>
                        </div>
                      </motion.div>
                    )}

                    <div className="relative mb-3">
                      <KeyRound className="absolute left-3.5 top-1/2 -translate-y-1/2 size-3.5 text-slate-600 pointer-events-none" />
                      <input
                        type={showKey ? "text" : "password"}
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder={t.inputPlaceholder}
                        disabled={submitting}
                        autoFocus
                        id="api-key"
                        className="login-input-control w-full h-11 pl-10 pr-10 bg-black/40 border border-cyan-500/15 rounded-lg text-white font-mono text-[0.8rem] box-border"
                      />
                      <button type="button" onClick={() => setShowKey(!showKey)} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-600 cursor-pointer p-1 bg-transparent border-none flex">
                        {showKey ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
                      </button>
                    </div>

                    <p className="text-[10px] text-slate-600 mb-4">{t.inputHint}</p>

                    <div className="remember-checkbox-row mb-4">
                      <Checkbox id="remember-c" checked={remember} onCheckedChange={(v) => setRemember(v === true)} disabled={submitting} className="border-slate-700 h-4 w-4 data-[state=checked]:bg-rose-500 data-[state=checked]:border-rose-500" />
                      <Label htmlFor="remember-c" className="text-[0.7rem] cursor-pointer text-slate-500 select-none">{t.rememberLabel}</Label>
                    </div>

                    <button type="submit" disabled={submitting || !apiKey.trim()} className="login-submit-btn w-full h-11 bg-gradient-to-r from-blue-600 to-purple-600 border-none rounded-lg text-white font-bold text-[0.8rem] cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-blue-600/30">
                      {submitting ? <><Loader2 className="size-4 animate-spin" />{t.submittingButton}</> : <><ShieldCheck className="size-4" />{t.submitButton}</>}
                    </button>

                    <div className="flex gap-2 mt-4">
                      <button type="button" onClick={() => setShowSupportModal(true)} className="flex-1 bg-transparent border border-white/8 rounded-lg py-1.5 text-[10px] font-semibold text-cyan-400 cursor-pointer transition-colors hover:bg-cyan-500/8">
                        {t.supportLink}
                      </button>
                      <button type="button" onClick={() => setShowRequestModal(true)} className="flex-1 bg-transparent border border-white/8 rounded-lg py-1.5 text-[10px] font-semibold text-red-400 cursor-pointer transition-colors hover:bg-red-500/8">
                        {t.requestAccessLink}
                      </button>
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
          </div>
        </motion.div>

        <div className="text-center mt-6 text-[10px] font-mono text-slate-600">
          AES-256 Encryption &middot; System v8.1 &middot; All connections secure
        </div>
      </motion.div>

      <LoginModal
        open={showSupportModal}
        onClose={() => setShowSupportModal(false)}
        title={t.supportTitle}
        icon={<HelpCircle className="size-5 text-cyan-400" />}
      >
        <p className="text-xs text-slate-300 leading-relaxed mb-4">{t.supportDesc}</p>
        <div className="text-[11px] font-mono bg-black/30 p-3 rounded-lg border border-cyan-500/10 text-slate-400 mb-4">{t.supportEmail}</div>
        <Button onClick={() => setShowSupportModal(false)} className="w-full bg-white/5 hover:bg-white/10 text-white text-xs h-9 border border-white/10">{t.closeBtn}</Button>
      </LoginModal>

      <LoginModal
        open={showRequestModal}
        onClose={() => setShowRequestModal(false)}
        title={t.requestTitle}
        icon={<Sparkles className="size-5 text-red-400" />}
      >
        <p className="text-xs text-slate-300 leading-relaxed mb-5">{t.requestDesc}</p>
        <Button onClick={handleAutoFillTestKey} className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold text-xs h-10 flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20 mb-3">
          <Sparkles className="size-4" />
          {t.autoFillDemoBtn}
        </Button>
        <Button onClick={() => setShowRequestModal(false)} className="w-full bg-white/5 hover:bg-white/10 text-white text-xs h-9 border border-white/10">{t.closeBtn}</Button>
      </LoginModal>
    </div>
  );
}
