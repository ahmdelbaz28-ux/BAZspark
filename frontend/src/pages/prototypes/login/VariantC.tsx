import {
	AlertCircle, Eye, EyeOff, Globe, KeyRound,
	Loader2, ShieldCheck, Sparkles, X,
} from "lucide-react";
import { type FormEvent, useEffect, useRef } from "react";
import { BazSparkLogo } from "@/components/auth/BazSparkLogo";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";

interface LoginVariantProps {
  lang: "en" | "ar";
  t: Record<string, string>;
  apiKey: string;
  setApiKey: (v: string) => void;
  showKey: boolean;
  setShowKey: (v: boolean) => void;
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

function ParticleCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    const particles: { x: number; y: number; vx: number; vy: number; r: number; a: number }[] = [];

    const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; };
    resize();
    window.addEventListener("resize", resize);

    for (let i = 0; i < 60; i++) {
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
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
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

    return () => { cancelAnimationFrame(animId); window.removeEventListener("resize", resize); };
  }, []);

  return <canvas ref={canvasRef} style={{ position: "absolute", inset: 0, pointerEvents: "none" }} />;
}

export function VariantC(props: LoginVariantProps) {
  const { lang, t, apiKey, setApiKey, showKey, setShowKey, submitting, error, isSuccess, showSupportModal, setShowSupportModal, showRequestModal, setShowRequestModal, handleSubmit, handleAutoFillTestKey, toggleLanguage } = props;

  return (
    <div dir={lang === "ar" ? "rtl" : "ltr"} style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", backgroundColor: "#020409", position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse 100% 60% at 50% 0%, rgba(6,78,112,0.15), transparent), radial-gradient(ellipse 80% 50% at 50% 100%, rgba(124,58,237,0.08), transparent)" }} />
      <ParticleCanvas />

      <div style={{ position: "absolute", top: "1.5rem", right: "2rem", zIndex: 10 }}>
        <button onClick={toggleLanguage} style={{ display: "flex", alignItems: "center", gap: "0.4rem", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "9999px", padding: "0.3rem 0.75rem", fontFamily: "monospace", fontSize: "0.65rem", fontWeight: 600, color: "#94a3b8", cursor: "pointer", backdropFilter: "blur(8px)" }}>
          <Globe style={{ width: "0.75rem", height: "0.75rem", color: "#38bdf8" }} />
          {lang === "en" ? "العربية" : "EN"}
        </button>
      </div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1 }} style={{ width: "100%", maxWidth: "440px", padding: "1rem", position: "relative", zIndex: 1 }}>
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.6 }} style={{ textAlign: "center", marginBottom: "2rem" }}>
          <motion.div initial={{ scale: 0.8 }} animate={{ scale: 1 }} transition={{ delay: 0.4, type: "spring", stiffness: 200 }}>
            <BazSparkLogo size={56} animated />
          </motion.div>
          <h1 style={{ fontSize: "1.75rem", fontWeight: 900, color: "#ffffff", marginTop: "1rem", letterSpacing: "-0.02em" }}>
            BAZSPARK
          </h1>
          <p style={{ fontSize: "0.7rem", color: "#64748b", fontFamily: "monospace", letterSpacing: "0.15em", marginTop: "0.25rem", textTransform: "uppercase" }}>
            {t.topBadge}
          </p>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5, duration: 0.6 }}>
          <div style={{ backgroundColor: "rgba(10,14,26,0.6)", border: "1px solid rgba(56,189,248,0.1)", borderRadius: "1rem", padding: "2rem", backdropFilter: "blur(16px)", boxShadow: "0 32px 64px rgba(0,0,0,0.5)" }}>
            <AnimatePresence mode="wait">
              {!isSuccess ? (
                <motion.div key="form" initial={{ opacity: 1 }} exit={{ opacity: 0, y: -10 }}>
                  <form onSubmit={handleSubmit}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.5rem" }}>
                      <div style={{ width: "0.25rem", height: "1.5rem", borderRadius: "9999px", background: "linear-gradient(180deg, #38bdf8, #7c3aed)" }} />
                      <div>
                        <div style={{ fontSize: "0.65rem", fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em" }}>{t.formTitle}</div>
                        <div style={{ fontSize: "0.7rem", color: "#94a3b8", marginTop: "0.1rem" }}>{t.formSubtitle}</div>
                      </div>
                    </div>

                    {error && (
                      <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} style={{ display: "flex", gap: "0.6rem", alignItems: "flex-start", backgroundColor: "rgba(244,63,94,0.1)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185", padding: "0.75rem", borderRadius: "0.5rem", fontSize: "0.7rem", marginBottom: "1rem" }} role="alert">
                        <AlertCircle style={{ width: "0.85rem", height: "0.85rem", flexShrink: 0, marginTop: "0.05rem" }} />
                        <div>
                          <div style={{ fontWeight: 700, fontSize: "0.6rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>Authentication Error</div>
                          <div style={{ marginTop: "0.1rem" }}>{error}</div>
                        </div>
                      </motion.div>
                    )}

                    <div style={{ position: "relative", marginBottom: "0.75rem" }}>
                      <KeyRound style={{ position: "absolute", left: "0.85rem", top: "50%", transform: "translateY(-50%)", width: "0.85rem", height: "0.85rem", color: "#475569", pointerEvents: "none" }} />
                      <input
                        type={showKey ? "text" : "password"}
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder={t.inputPlaceholder}
                        disabled={submitting}
                        autoFocus
                        style={{ width: "100%", height: "2.75rem", paddingLeft: "2.5rem", paddingRight: "2.5rem", backgroundColor: "rgba(0,0,0,0.4)", border: "1px solid rgba(56,189,248,0.15)", borderRadius: "0.5rem", color: "#ffffff", fontFamily: "monospace", fontSize: "0.8rem", boxSizing: "border-box", transition: "border-color 0.3s, box-shadow 0.3s" }}
                        onFocus={(e) => { e.target.style.borderColor = "#38bdf8"; e.target.style.boxShadow = "0 0 0 3px rgba(56,189,248,0.1)"; e.target.style.outline = "none"; }}
                        onBlur={(e) => { e.target.style.borderColor = "rgba(56,189,248,0.15)"; e.target.style.boxShadow = "none"; }}
                      />
                      <button type="button" onClick={() => setShowKey(!showKey)} style={{ position: "absolute", right: "0.85rem", top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: "#475569", cursor: "pointer", padding: "0.2rem", display: "flex" }}>
                        {showKey ? <EyeOff style={{ width: "0.85rem", height: "0.85rem" }} /> : <Eye style={{ width: "0.85rem", height: "0.85rem" }} />}
                      </button>
                    </div>

                    <p style={{ fontSize: "0.6rem", color: "#475569", marginBottom: "1.25rem" }}>{t.inputHint}</p>

                    <button type="submit" disabled={submitting || !apiKey.trim()} style={{ width: "100%", height: "2.75rem", background: "linear-gradient(135deg, #2563eb, #7c3aed)", border: "none", borderRadius: "0.5rem", color: "#ffffff", fontWeight: 700, fontSize: "0.8rem", cursor: submitting ? "not-allowed" : "pointer", opacity: submitting ? 0.6 : 1, display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem", transition: "opacity 0.2s", boxShadow: "0 8px 24px rgba(37,99,235,0.3)" }}>
                      {submitting ? <><Loader2 className="animate-spin" style={{ width: "1rem", height: "1rem" }} />{t.submittingButton}</> : <><ShieldCheck style={{ width: "1rem", height: "1rem" }} />{t.submitButton}</>}
                    </button>

                    <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
                      <button type="button" onClick={() => setShowSupportModal(true)} style={{ flex: 1, background: "none", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "0.5rem", padding: "0.4rem", fontSize: "0.6rem", fontWeight: 600, color: "#38bdf8", cursor: "pointer", transition: "background 0.2s" }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(56,189,248,0.08)"; }} onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}>
                        {t.supportLink}
                      </button>
                      <button type="button" onClick={() => setShowRequestModal(true)} style={{ flex: 1, background: "none", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "0.5rem", padding: "0.4rem", fontSize: "0.6rem", fontWeight: 600, color: "#f87171", cursor: "pointer", transition: "background 0.2s" }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(248,113,113,0.08)"; }} onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}>
                        {t.requestAccessLink}
                      </button>
                    </div>
                  </form>
                </motion.div>
              ) : (
                <motion.div key="success" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ type: "spring", stiffness: 200 }} style={{ textAlign: "center", padding: "2rem 1rem" }}>
                  <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 0.2, type: "spring", stiffness: 300 }} style={{ width: "4rem", height: "4rem", borderRadius: "9999px", background: "linear-gradient(135deg, rgba(6,78,59,0.9), rgba(5,150,105,0.4))", border: "1px solid rgba(52,211,153,0.3)", display: "flex", alignItems: "center", justifyContent: "center", color: "#34d399", margin: "0 auto 1rem", boxShadow: "0 0 30px rgba(52,211,153,0.15)" }}>
                    <ShieldCheck style={{ width: "2rem", height: "2rem" }} />
                  </motion.div>
                  <motion.h3 initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }} style={{ fontSize: "1.125rem", fontWeight: 700, color: "#ffffff" }}>{t.accessGranted}</motion.h3>
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }} style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.25rem" }}>{t.sessionInitialized}</motion.p>
                  <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 }} style={{ display: "block", marginTop: "0.75rem", fontSize: "0.6rem", fontFamily: "monospace", letterSpacing: "0.1em", color: "#34d399" }}>{t.redirecting}</motion.span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>

        <div style={{ textAlign: "center", marginTop: "1.5rem", fontSize: "0.6rem", fontFamily: "monospace", color: "#475569" }}>
          AES-256 Encryption · System v8.1 · All connections secure
        </div>
      </motion.div>

      <AnimatePresence>
        {showSupportModal && (
          <div style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem", backgroundColor: "rgba(0,0,0,0.8)", backdropFilter: "blur(8px)" }}>
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }} style={{ width: "100%", maxWidth: "400px", backgroundColor: "rgba(10,14,26,0.95)", border: "1px solid rgba(56,189,248,0.15)", borderRadius: "1rem", padding: "1.5rem", boxShadow: "0 32px 64px rgba(0,0,0,0.5)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h3 style={{ fontSize: "0.9rem", fontWeight: 700, color: "#ffffff" }}>{t.supportTitle}</h3>
                <button onClick={() => setShowSupportModal(false)} style={{ background: "none", border: "none", color: "#64748b", cursor: "pointer" }}><X style={{ width: "1rem", height: "1rem" }} /></button>
              </div>
              <p style={{ fontSize: "0.75rem", color: "#cbd5e1", lineHeight: 1.5, marginBottom: "1rem" }}>{t.supportDesc}</p>
              <div style={{ fontSize: "0.7rem", fontFamily: "monospace", backgroundColor: "rgba(0,0,0,0.3)", padding: "0.75rem", borderRadius: "0.5rem", border: "1px solid rgba(56,189,248,0.1)", color: "#94a3b8", marginBottom: "1rem" }}>{t.supportEmail}</div>
              <Button onClick={() => setShowSupportModal(false)} className="w-full bg-white/5 hover:bg-white/10 text-white text-xs h-9 border border-white/10">{t.closeBtn}</Button>
            </motion.div>
          </div>
        )}
        {showRequestModal && (
          <div style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem", backgroundColor: "rgba(0,0,0,0.8)", backdropFilter: "blur(8px)" }}>
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }} style={{ width: "100%", maxWidth: "400px", backgroundColor: "rgba(10,14,26,0.95)", border: "1px solid rgba(248,113,113,0.15)", borderRadius: "1rem", padding: "1.5rem", boxShadow: "0 32px 64px rgba(0,0,0,0.5)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h3 style={{ fontSize: "0.9rem", fontWeight: 700, color: "#ffffff" }}>{t.requestTitle}</h3>
                <button onClick={() => setShowRequestModal(false)} style={{ background: "none", border: "none", color: "#64748b", cursor: "pointer" }}><X style={{ width: "1rem", height: "1rem" }} /></button>
              </div>
              <p style={{ fontSize: "0.75rem", color: "#cbd5e1", lineHeight: 1.5, marginBottom: "1.25rem" }}>{t.requestDesc}</p>
              <Button onClick={handleAutoFillTestKey} className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold text-xs h-10 flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20 mb-3">
                <Sparkles style={{ width: "1rem", height: "1rem" }} />
                {t.autoFillDemoBtn}
              </Button>
              <Button onClick={() => setShowRequestModal(false)} className="w-full bg-white/5 hover:bg-white/10 text-white text-xs h-9 border border-white/10">{t.closeBtn}</Button>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}