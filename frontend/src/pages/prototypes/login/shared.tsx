/**
 * shared.tsx — Shared sub-components for Login Variant components
 *
 * Eliminates ~226 lines of duplication across VariantA/B/C by extracting
 * common UI patterns: error alert, API key input, success view, modals,
 * remember checkbox, and language toggle.
 */

import {
        AlertCircle,
        Eye,
        EyeOff,
        Globe,
        HelpCircle,
        KeyRound,
        Loader2,
        ShieldCheck,
        Sparkles,
        X,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
// LoginVariantProps type is used by sub-components that need access to the full props shape

// ── Error Alert ─────────────────────────────────────────────────────────

interface ErrorAlertProps {
        readonly lang: "en" | "ar";
        readonly error: string | null;
}

export function LoginErrorAlert({ lang, error }: ErrorAlertProps) {
        if (!error) return null;
        return (
                <div
                        style={{
                                display: "flex",
                                gap: "0.6rem",
                                alignItems: "flex-start",
                                backgroundColor: "rgba(244, 63, 94, 0.1)",
                                border: "1px solid rgba(244, 63, 94, 0.25)",
                                color: "#fb7185",
                                padding: "0.75rem 1rem",
                                borderRadius: "0.5rem",
                                fontSize: "0.75rem",
                                marginBottom: "1rem",
                        }}
                        role="alert"
                >
                        <AlertCircle
                                aria-hidden="true"
                                style={{ width: "1rem", height: "1rem", flexShrink: 0, marginTop: "0.1rem" }}
                        />
                        <div>
                                <div
                                        style={{
                                                fontWeight: 700,
                                                textTransform: "uppercase",
                                                letterSpacing: "0.05em",
                                                fontSize: "0.6rem",
                                        }}
                                >
                                        {lang === "ar" ? "فشل تسجيل الدخول" : "Sign-in failed"}
                                </div>
                                <div style={{ opacity: 0.9, marginTop: "0.1rem" }}>{error}</div>
                        </div>
                </div>
        );
}

// ── API Key Input Field ─────────────────────────────────────────────────

interface ApiKeyInputProps {
        readonly t: Record<string, string>;
        readonly apiKey: string;
        readonly setApiKey: (v: string) => void;
        readonly showKey: boolean;
        readonly setShowKey: (v: boolean) => void;
        readonly submitting: boolean;
}

export function ApiKeyInputField({
        t,
        apiKey,
        setApiKey,
        showKey,
        setShowKey,
        submitting,
}: ApiKeyInputProps) {
        return (
                <div style={{ position: "relative", marginBottom: "0.5rem" }}>
                        <KeyRound
                                aria-hidden="true"
                                style={{
                                        position: "absolute",
                                        left: "0.85rem",
                                        top: "50%",
                                        transform: "translateY(-50%)",
                                        width: "0.9rem",
                                        height: "0.9rem",
                                        color: "#94a3b8",
                                        pointerEvents: "none",
                                }}
                        />
                        <input
                                id="api-key"
                                type={showKey ? "text" : "password"}
                                name="api_key"
                                autoComplete="off"
                                autoFocus
                                placeholder={t.inputPlaceholder}
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                disabled={submitting}
                                aria-label={t.inputLabel}
                                aria-required="true"
                                aria-invalid={Boolean(apiKey) && apiKey.length < 4}
                                style={{
                                        width: "100%",
                                        height: "2.75rem",
                                        paddingLeft: "2.5rem",
                                        paddingRight: "2.5rem",
                                        backgroundColor: "#050811",
                                        border: "1px solid #1e293b",
                                        borderRadius: "0.5rem",
                                        color: "#ffffff",
                                        fontFamily: "monospace",
                                        fontSize: "0.8rem",
                                        boxSizing: "border-box",
                                        transition: "border-color 0.2s, box-shadow 0.2s",
                                }}
                                onFocus={(e) => {
                                        e.target.style.borderColor = "#22d3ee";
                                        e.target.style.boxShadow = "0 0 0 3px rgba(34, 211, 238, 0.2)";
                                        e.target.style.outline = "none";
                                }}
                                onBlur={(e) => {
                                        e.target.style.borderColor = "#1e293b";
                                        e.target.style.boxShadow = "none";
                                }}
                        />
                        <button
                                type="button"
                                onClick={() => setShowKey(!showKey)}
                                style={{
                                        position: "absolute",
                                        right: "0.85rem",
                                        top: "50%",
                                        transform: "translateY(-50%)",
                                        background: "none",
                                        border: "none",
                                        color: "#94a3b8",
                                        cursor: "pointer",
                                        padding: "0.2rem",
                                        display: "flex",
                                }}
                                aria-label={showKey ? "Hide API key" : "Show API key"}
                                tabIndex={-1}
                        >
                                {showKey ? (
                                        <EyeOff aria-hidden="true" style={{ width: "1rem", height: "1rem" }} />
                                ) : (
                                        <Eye aria-hidden="true" style={{ width: "1rem", height: "1rem" }} />
                                )}
                        </button>
                </div>
        );
}

// ── Submit Button ───────────────────────────────────────────────────────

interface SubmitButtonProps {
        readonly t: Record<string, string>;
        readonly submitting: boolean;
        readonly disabled: boolean;
}

export function LoginSubmitButton({ t, submitting, disabled }: SubmitButtonProps) {
        return (
                <button
                        type="submit"
                        disabled={disabled}
                        data-testid="initialize-session-btn"
                        style={{
                                width: "100%",
                                height: "2.75rem",
                                backgroundColor: "#22d3ee",
                                border: "none",
                                borderRadius: "0.5rem",
                                color: "#070b12",
                                fontWeight: 700,
                                fontSize: "0.8rem",
                                cursor: submitting ? "not-allowed" : "pointer",
                                opacity: submitting || disabled ? 0.6 : 1,
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                gap: "0.5rem",
                                transition: "background-color 0.2s, box-shadow 0.2s, transform 0.1s",
                                boxShadow: "0 8px 16px rgba(34, 211, 238, 0.25)",
                        }}
                        onMouseEnter={(e) => {
                                if (!submitting && !disabled) {
                                        e.currentTarget.style.backgroundColor = "#67e8f9";
                                        e.currentTarget.style.boxShadow = "0 10px 20px rgba(34, 211, 238, 0.35)";
                                }
                        }}
                        onMouseLeave={(e) => {
                                e.currentTarget.style.backgroundColor = "#22d3ee";
                                e.currentTarget.style.boxShadow = "0 8px 16px rgba(34, 211, 238, 0.25)";
                        }}
                >
                        {submitting ? (
                                <>
                                        <Loader2 className="animate-spin" style={{ width: "1rem", height: "1rem" }} />
                                        {t.submittingButton}
                                </>
                        ) : (
                                <>
                                        <ShieldCheck aria-hidden="true" style={{ width: "1rem", height: "1rem" }} />
                                        {t.submitButton}
                                </>
                        )}
                </button>
        );
}

// ── Success View ────────────────────────────────────────────────────────

interface SuccessViewProps {
        readonly t: Record<string, string>;
}

export function LoginSuccessView({ t }: SuccessViewProps) {
        return (
                <motion.div
                        key="success-view"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        style={{
                                textAlign: "center",
                                padding: "2.5rem 1.5rem",
                                backgroundColor: "rgba(7, 11, 22, 0.9)",
                                border: "1px solid rgba(52, 211, 153, 0.2)",
                                borderRadius: "0.75rem",
                                display: "flex",
                                flexDirection: "column",
                                alignItems: "center",
                                gap: "1rem",
                        }}
                >
                        <div
                                style={{
                                        width: "4rem",
                                        height: "4rem",
                                        borderRadius: "9999px",
                                        backgroundColor: "rgba(6, 78, 59, 0.8)",
                                        border: "1px solid rgba(52, 211, 153, 0.3)",
                                        display: "flex",
                                        alignItems: "center",
                                        color: "#34d399",
                                }}
                        >
                                <ShieldCheck style={{ width: "2rem", height: "2rem", margin: "auto" }} />
                        </div>
                        <div>
                                <h3 style={{ fontSize: "1.125rem", fontWeight: 700, color: "#ffffff" }}>
                                        {t.accessGranted}
                                </h3>
                                <p style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.25rem" }}>
                                        {t.sessionInitialized}
                                </p>
                        </div>
                        <span
                                style={{
                                        fontSize: "0.6rem",
                                        fontFamily: "monospace",
                                        letterSpacing: "0.1em",
                                        color: "#34d399",
                                        textTransform: "uppercase",
                                }}
                        >
                                {t.redirecting}
                        </span>
                </motion.div>
        );
}

// ── Remember Me Checkbox ────────────────────────────────────────────────

interface RememberCheckboxProps {
        readonly t: Record<string, string>;
        readonly remember: boolean;
        readonly setRemember: (v: boolean) => void;
        readonly submitting: boolean;
}

export function RememberCheckbox({ t, remember, setRemember, submitting }: RememberCheckboxProps) {
        return (
                <div className="remember-checkbox-row" style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.75rem", marginBottom: "1rem" }}>
                        <Checkbox
                                id="remember"
                                checked={remember}
                                onCheckedChange={(v) => setRemember(v === true)}
                                disabled={submitting}
                                className="border-slate-800 h-4 w-4 data-[state=checked]:bg-rose-500 data-[state=checked]:border-rose-500"
                        />
                        <Label
                                htmlFor="remember"
                                style={{ fontSize: "0.775rem", cursor: "pointer", color: "#94a3b8", userSelect: "none" }}
                        >
                                {t.rememberLabel}
                        </Label>
                </div>
        );
}

// ── Support Modal ───────────────────────────────────────────────────────

interface SupportModalProps {
        readonly t: Record<string, string>;
        readonly showSupportModal: boolean;
        readonly setShowSupportModal: (v: boolean) => void;
}

export function SupportModal({ t, showSupportModal, setShowSupportModal }: SupportModalProps) {
        return (
                <AnimatePresence>
                        {showSupportModal && (
                                <div
                                        style={{
                                                position: "fixed",
                                                inset: 0,
                                                zIndex: 50,
                                                display: "flex",
                                                alignItems: "center",
                                                padding: "1rem",
                                                backgroundColor: "rgba(0, 0, 0, 0.75)",
                                                backdropFilter: "blur(4px)",
                                        }}
                                >
                                        <motion.div
                                                initial={{ opacity: 0, scale: 0.95 }}
                                                animate={{ opacity: 1, scale: 1 }}
                                                exit={{ opacity: 0, scale: 0.95 }}
                                                style={{
                                                        width: "100%",
                                                        maxWidth: "420px",
                                                        backgroundColor: "#0a0f1d",
                                                        border: "1px solid #1e293b",
                                                        borderRadius: "0.75rem",
                                                        padding: "1.5rem",
                                                        boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7)",
                                                        margin: "auto",
                                                }}
                                        >
                                                <div
                                                        style={{
                                                                display: "flex",
                                                                alignItems: "center",
                                                                justifyContent: "space-between",
                                                                borderBottom: "1px solid #1e293b",
                                                                paddingBottom: "0.75rem",
                                                                marginBottom: "1rem",
                                                        }}
                                                >
                                                        <h3
                                                                style={{
                                                                        fontSize: "1rem",
                                                                        fontWeight: 700,
                                                                        color: "#ffffff",
                                                                        display: "flex",
                                                                        alignItems: "center",
                                                                        gap: "0.5rem",
                                                                }}
                                                        >
                                                                <HelpCircle style={{ width: "1.25rem", height: "1.25rem", color: "#38bdf8" }} />
                                                                {t.supportTitle}
                                                        </h3>
                                                        <button
                                                                type="button"
                                                                onClick={() => setShowSupportModal(false)}
                                                                style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", padding: "0.2rem" }}
                                                        >
                                                                <X style={{ width: "1rem", height: "1rem" }} />
                                                        </button>
                                                </div>
                                                <p style={{ fontSize: "0.775rem", color: "#cbd5e1", lineHeight: 1.5, marginBottom: "1rem" }}>
                                                        {t.supportDesc}
                                                </p>
                                                <div
                                                        style={{
                                                                fontSize: "0.75rem",
                                                                fontFamily: "monospace",
                                                                backgroundColor: "#050811",
                                                                padding: "0.75rem",
                                                                borderRadius: "0.5rem",
                                                                border: "1px solid #1e293b",
                                                                color: "#94a3b8",
                                                                marginBottom: "1.25rem",
                                                        }}
                                                >
                                                        <div>{t.supportEmail}</div>
                                                        <div style={{ marginTop: "0.25rem" }}>Standard Format: BS-XXXX-XXXX-XXXX-XXXX</div>
                                                </div>
                                                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                                                        <Button
                                                                type="button"
                                                                onClick={() => setShowSupportModal(false)}
                                                                className="bg-slate-800 hover:bg-slate-700 text-white text-xs px-4 h-9"
                                                        >
                                                                {t.closeBtn}
                                                        </Button>
                                                </div>
                                        </motion.div>
                                </div>
                        )}
                </AnimatePresence>
        );
}

// ── Request Access Modal ────────────────────────────────────────────────

interface RequestAccessModalProps {
        readonly t: Record<string, string>;
        readonly showRequestModal: boolean;
        readonly setShowRequestModal: (v: boolean) => void;
        readonly handleAutoFillTestKey: () => void;
}

export function RequestAccessModal({
        t,
        showRequestModal,
        setShowRequestModal,
        handleAutoFillTestKey,
}: RequestAccessModalProps) {
        return (
                <AnimatePresence>
                        {showRequestModal && (
                                <div
                                        style={{
                                                position: "fixed",
                                                inset: 0,
                                                zIndex: 50,
                                                display: "flex",
                                                alignItems: "center",
                                                padding: "1rem",
                                                backgroundColor: "rgba(0, 0, 0, 0.75)",
                                                backdropFilter: "blur(4px)",
                                        }}
                                >
                                        <motion.div
                                                initial={{ opacity: 0, scale: 0.95 }}
                                                animate={{ opacity: 1, scale: 1 }}
                                                exit={{ opacity: 0, scale: 0.95 }}
                                                style={{
                                                        width: "100%",
                                                        maxWidth: "420px",
                                                        backgroundColor: "#0a0f1d",
                                                        border: "1px solid #1e293b",
                                                        borderRadius: "0.75rem",
                                                        padding: "1.5rem",
                                                        boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7)",
                                                        margin: "auto",
                                                }}
                                        >
                                                <div
                                                        style={{
                                                                display: "flex",
                                                                alignItems: "center",
                                                                justifyContent: "space-between",
                                                                borderBottom: "1px solid #1e293b",
                                                                paddingBottom: "0.75rem",
                                                                marginBottom: "1rem",
                                                        }}
                                                >
                                                        <h3
                                                                style={{
                                                                        fontSize: "1rem",
                                                                        fontWeight: 700,
                                                                        color: "#ffffff",
                                                                        display: "flex",
                                                                        alignItems: "center",
                                                                        gap: "0.5rem",
                                                                }}
                                                        >
                                                                <Sparkles style={{ width: "1.25rem", height: "1.25rem", color: "#f87171" }} />
                                                                {t.requestTitle}
                                                        </h3>
                                                        <button
                                                                type="button"
                                                                onClick={() => setShowRequestModal(false)}
                                                                style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", padding: "0.2rem" }}
                                                        >
                                                                <X style={{ width: "1rem", height: "1rem" }} />
                                                        </button>
                                                </div>
                                                <p style={{ fontSize: "0.775rem", color: "#cbd5e1", lineHeight: 1.5, marginBottom: "1.25rem" }}>
                                                        {t.requestDesc}
                                                </p>
                                                <Button
                                                        type="button"
                                                        onClick={handleAutoFillTestKey}
                                                        className="w-full bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs h-10 tracking-wider flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20 mb-4"
                                                >
                                                        <Sparkles style={{ width: "1rem", height: "1rem" }} />
                                                        {t.autoFillDemoBtn}
                                                </Button>
                                                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                                                        <Button
                                                                type="button"
                                                                onClick={() => setShowRequestModal(false)}
                                                                className="bg-slate-800 hover:bg-slate-700 text-white text-xs px-4 h-9"
                                                        >
                                                                {t.closeBtn}
                                                        </Button>
                                                </div>
                                        </motion.div>
                                </div>
                        )}
                </AnimatePresence>
        );
}

// ── Language Toggle ─────────────────────────────────────────────────────

interface LanguageToggleProps {
        readonly lang: "en" | "ar";
        readonly toggleLanguage: () => void;
}

export function LanguageToggle({ lang, toggleLanguage }: LanguageToggleProps) {
        return (
                <button
                        type="button"
                        onClick={toggleLanguage}
                        className="lang-toggle-btn"
                        aria-label="Switch Language"
                        style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "0.4rem",
                                background: "rgba(12,17,32,0.8)",
                                border: "1px solid rgba(30,41,59,0.9)",
                                borderRadius: "0.5rem",
                                padding: "0.3rem 0.65rem",
                                fontFamily: "monospace",
                                fontSize: "0.7rem",
                                fontWeight: 700,
                                color: "#cbd5e1",
                                cursor: "pointer",
                        }}
                >
                        <Globe aria-hidden="true" style={{ width: "0.9rem", height: "0.9rem", color: "#38bdf8" }} />
                        <span style={{ color: lang === "en" ? "#38bdf8" : "#94a3b8" }}>EN</span>
                        <span style={{ color: "#475569" }}>|</span>
                        <span style={{ color: lang === "ar" ? "#38bdf8" : "#94a3b8" }}>العربية</span>
                </button>
        );
}
