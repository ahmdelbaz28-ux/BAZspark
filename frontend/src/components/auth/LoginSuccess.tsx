import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";

interface LoginSuccessProps {
  accessGranted: string;
  sessionInitialized: string;
  redirecting: string;
  variant?: "default" | "dark";
}

export function LoginSuccess({ accessGranted, sessionInitialized, redirecting, variant = "default" }: LoginSuccessProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    containerRef.current?.focus();
  }, []);

  return (
    <motion.div
      ref={containerRef}
      key="login-success"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="text-center p-10 flex flex-col items-center gap-4"
      tabIndex={-1}
      role="status"
      aria-live="polite"
    >
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ delay: 0.15, type: "spring", stiffness: 200 }}
        className="size-16 rounded-full bg-emerald-900/80 border border-emerald-500/30 flex items-center text-emerald-400"
      >
        <ShieldCheck className="size-8 m-auto" />
      </motion.div>
      <div>
        <h3 className="text-lg font-bold text-white">{accessGranted}</h3>
        <p className="text-xs text-slate-400 mt-1">{sessionInitialized}</p>
      </div>
      <motion.span
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
        className="text-[0.6rem] font-mono tracking-widest text-emerald-400 uppercase"
      >
        {redirecting}
      </motion.span>
    </motion.div>
  );
}
