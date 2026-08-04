/** @internal Design prototype — excluded from production via PrototypeSwitcher feature flag */

/**
 * VariantB.tsx — Minimal SaaS Login
 *
 * Refactored to use shared LoginVariantProps and shared sub-components.
 * Now includes the Remember Me checkbox (was missing before).
 */

import { BazSparkLogo, BazSparkWordmark } from "@/components/auth/BazSparkLogo";
import { motion, AnimatePresence } from "framer-motion";
import type { LoginVariantProps } from "./types";
import {
        LoginErrorAlert,
        ApiKeyInputField,
        LoginSubmitButton,
        LoginSuccessView,
        RememberCheckbox,
        SupportModal,
        RequestAccessModal,
        LanguageToggle,
} from "./shared";

export function VariantB(props: Readonly<LoginVariantProps>) {
        const {
                lang,
                t,
                apiKey,
                setApiKey,
                showKey,
                setShowKey,
                remember,
                setRemember,
                submitting,
                error,
                isSuccess,
                showSupportModal,
                setShowSupportModal,
                showRequestModal,
                setShowRequestModal,
                handleSubmit,
                handleAutoFillTestKey,
                toggleLanguage,
        } = props;

        return (
                <div
                        dir={lang === "ar" ? "rtl" : "ltr"}
                        style={{
                                minHeight: "100vh",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                backgroundColor: "#070b16",
                                padding: "1rem",
                                position: "relative",
                                overflow: "hidden",
                        }}
                >
                        <div
                                style={{
                                        position: "absolute",
                                        inset: 0,
                                        background: "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(56,189,248,0.06), transparent)",
                                }}
                        />

                        <div style={{ position: "absolute", top: "1.5rem", right: "2rem", zIndex: 10 }}>
                                <LanguageToggle lang={lang} toggleLanguage={toggleLanguage} />
                        </div>

                        <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.5 }}
                                style={{ width: "100%", maxWidth: "420px" }}
                        >
                                <div
                                        style={{
                                                display: "flex",
                                                flexDirection: "column",
                                                alignItems: "center",
                                                textAlign: "center",
                                                marginBottom: "2rem",
                                        }}
                                >
                                        <div style={{ marginBottom: "1rem" }}>
                                                <BazSparkLogo size={48} animated />
                                        </div>
                                        <BazSparkWordmark size="lg" />
                                        <p
                                                style={{
                                                        fontSize: "0.8rem",
                                                        color: "#94a3b8",
                                                        marginTop: "0.5rem",
                                                        fontFamily: "monospace",
                                                        letterSpacing: "0.1em",
                                                }}
                                        >
                                                {t.topBadge}
                                        </p>
                                </div>

                                <div
                                        style={{
                                                backgroundColor: "rgba(10,14,26,0.8)",
                                                border: "1px solid rgba(30,41,59,0.7)",
                                                borderRadius: "1rem",
                                                padding: "2rem",
                                                backdropFilter: "blur(12px)",
                                        }}
                                >
                                        <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#ffffff", marginBottom: "0.3rem" }}>
                                                {t.formTitle}
                                        </h2>
                                        <p style={{ fontSize: "0.8rem", color: "#94a3b8", marginBottom: "1.5rem" }}>{t.formSubtitle}</p>

                                        <AnimatePresence mode="wait">
                                                {!isSuccess ? (
                                                        <motion.div key="form-view" initial={{ opacity: 1 }} exit={{ opacity: 0, y: -12 }}>
                                                                <form onSubmit={handleSubmit}>
                                                                        <LoginErrorAlert lang={lang} error={error} />

                                                                        <label
                                                                                style={{
                                                                                        display: "block",
                                                                                        fontSize: "0.65rem",
                                                                                        fontWeight: 600,
                                                                                        color: "#94a3b8",
                                                                                        textTransform: "uppercase",
                                                                                        letterSpacing: "0.08em",
                                                                                        marginBottom: "0.4rem",
                                                                                }}
                                                                        >
                                                                                {t.inputLabel}
                                                                        </label>
                                                                        <ApiKeyInputField t={t} apiKey={apiKey} setApiKey={setApiKey} showKey={showKey} setShowKey={setShowKey} submitting={submitting} />
                                                                        <p style={{ fontSize: "0.65rem", color: "#475569", marginBottom: "0.25rem" }}>{t.inputHint}</p>

                                                                        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem", marginBottom: "1.25rem" }}>
                                                                                <button
                                                                                        type="button"
                                                                                        onClick={() => setShowSupportModal(true)}
                                                                                        style={{
                                                                                                flex: 1,
                                                                                                background: "none",
                                                                                                border: "1px solid #1e293b",
                                                                                                borderRadius: "0.5rem",
                                                                                                padding: "0.4rem",
                                                                                                fontSize: "0.65rem",
                                                                                                fontWeight: 600,
                                                                                                color: "#38bdf8",
                                                                                                cursor: "pointer",
                                                                                        }}
                                                                                >
                                                                                        {t.supportLink}
                                                                                </button>
                                                                                <button
                                                                                        type="button"
                                                                                        onClick={() => setShowRequestModal(true)}
                                                                                        style={{
                                                                                                flex: 1,
                                                                                                background: "none",
                                                                                                border: "1px solid #1e293b",
                                                                                                borderRadius: "0.5rem",
                                                                                                padding: "0.4rem",
                                                                                                fontSize: "0.65rem",
                                                                                                fontWeight: 600,
                                                                                                color: "#f87171",
                                                                                                cursor: "pointer",
                                                                                        }}
                                                                                >
                                                                                        {t.requestAccessLink}
                                                                                </button>
                                                                        </div>

                                                                        <RememberCheckbox t={t} remember={remember} setRemember={setRemember} submitting={submitting} />
                                                                        <LoginSubmitButton t={t} submitting={submitting} disabled={submitting || !apiKey.trim()} />
                                                                </form>
                                                        </motion.div>
                                                ) : (
                                                        <LoginSuccessView t={t} />
                                                )}
                                        </AnimatePresence>
                                </div>

                                <div style={{ textAlign: "center", marginTop: "1.5rem", fontSize: "0.65rem", fontFamily: "monospace", color: "#475569" }}>
                                        <span style={{ color: "#34d399" }}>AES-256</span> · System v8.1
                                </div>
                        </motion.div>

                        <SupportModal t={t} showSupportModal={showSupportModal} setShowSupportModal={setShowSupportModal} />
                        <RequestAccessModal t={t} showRequestModal={showRequestModal} setShowRequestModal={setShowRequestModal} handleAutoFillTestKey={handleAutoFillTestKey} />
                </div>
        );
}
