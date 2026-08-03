/**
 * VariantA.tsx — Engineering Terminal Login (Production Design)
 *
 * Refactored to use shared LoginVariantProps and shared sub-components.
 * Only layout-specific code remains in this file.
 *
 * Phase 12 (frontend-design skill): the signature alarm status bar is wired
 * here. The bar's color class is derived from the form state:
 *   - idle       → green at 70% (system secure, awaiting input)
 *   - submitting → amber with 1.6s two-stroke pulse (acknowledged)
 *   - error      → signal-red solid (life-safety alarm / auth fail)
 *   - isSuccess  → green solid + 600ms glow (session initialized)
 *
 * The bar is rendered as the FIRST child of <main> so it sits at the very
 * top of the viewport. CSS in login.css handles the position:fixed styling
 * and the prefers-reduced-motion fallback.
 */

import { Anchor, Bot, Compass, Layers, Lock, ShieldCheck } from "lucide-react";
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

export function VariantA(props: Readonly<LoginVariantProps>) {
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

        // Derive alarm status bar state from form state.
        // Order matters: error > submitting > success > idle.
        const alarmState = error
                ? "alarm-state-error"
                : submitting
                        ? "alarm-state-submitting"
                        : isSuccess
                                ? "alarm-state-success"
                                : "alarm-state-idle";

        // Screen-reader announcements must match the UI language (per the
        // frontend-design skill's "Language Consistency Rule"). These four
        // status phrases are the spoken equivalent of the bar's color.
        const alarmAriaLabel = error
                ? (lang === "ar" ? "فشل المصادقة" : "Authentication failed")
                : submitting
                        ? (lang === "ar" ? "جاري المصادقة" : "Authenticating")
                        : isSuccess
                                ? (lang === "ar" ? "تم بدء الجلسة" : "Session initialized")
                                : (lang === "ar" ? "النظام آمن" : "System secure");

        const features = [
                { icon: <Compass style={{ width: "1.25rem", height: "1.25rem" }} />, cls: "icon-box-cad", title: t.feature1Title, desc: t.feature1Desc },
                { icon: <ShieldCheck style={{ width: "1.25rem", height: "1.25rem" }} />, cls: "icon-box-compliance", title: t.feature2Title, desc: t.feature2Desc },
                { icon: <Layers style={{ width: "1.25rem", height: "1.25rem" }} />, cls: "icon-box-bim", title: t.feature3Title, desc: t.feature3Desc },
                { icon: <Bot style={{ width: "1.25rem", height: "1.25rem" }} />, cls: "icon-box-ai", title: t.feature4Title, desc: t.feature4Desc },
                { icon: <Anchor style={{ width: "1.25rem", height: "1.25rem" }} />, cls: "icon-box-marine", title: t.feature5Title, desc: t.feature5Desc },
        ];

        return (
                <main
                        className={`login-screen-root ${lang === "ar" ? "rtl" : "ltr"}`}
                        dir={lang === "ar" ? "rtl" : "ltr"}
                        aria-label="BAZSPARK Login"
                >
                        {/* Signature element: alarm status bar.
                            State-driven (NOT decorative). See login.css for the
                            color vocabulary and pulse cadence. The aria-live region
                            announces state changes to screen readers without
                            hijacking focus. */}
                        <div
                                className={`alarm-status-bar ${alarmState}`}
                                role="status"
                                aria-live="polite"
                                aria-label={alarmAriaLabel}
                        />

                        <header className="login-header-lang">
                                <LanguageToggle lang={lang} toggleLanguage={toggleLanguage} />
                        </header>

                        <div className="login-split-container">
                                <div className="login-left-panel">
                                        <div style={{ width: "100%", maxWidth: "580px", margin: "auto 0" }}>
                                                <div className="login-logo-card">
                                                        <BazSparkLogo size={42} animated />
                                                        <div style={{ display: "flex", flexDirection: "column" }}>
                                                                <BazSparkWordmark size="md" />
                                                                <span
                                                                        style={{
                                                                                fontSize: "0.6rem",
                                                                                fontFamily: "var(--font-data)",
                                                                                fontWeight: 500,
                                                                                letterSpacing: "0.15em",
                                                                                color: "var(--color-steel)",
                                                                                textTransform: "uppercase",
                                                                                marginTop: "0.15rem",
                                                                        }}
                                                                >
                                                                        {t.topBadge}
                                                                </span>
                                                        </div>
                                                </div>
                                                <h1 className="login-hero-title">{t.heroTitle}</h1>
                                                <p className="login-hero-subtitle">{t.heroSubtitle}</p>
                                                <div className="login-feature-list">
                                                        {features.map((f, idx) => (
                                                                <div
                                                                        key={f.cls}
                                                                        className="login-feature-item"
                                                                        data-index={String(idx + 1).padStart(2, "0")}
                                                                >
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
                                                                                        <LoginErrorAlert lang={lang} error={error} />
                                                                                        <div className="input-label-row">
                                                                                                <span>{t.inputLabel}</span>
                                                                                                <button type="button" onClick={() => setShowSupportModal(true)} className="support-link-btn">
                                                                                                        {t.supportLink}
                                                                                                </button>
                                                                                        </div>
                                                                                        <ApiKeyInputField t={t} apiKey={apiKey} setApiKey={setApiKey} showKey={showKey} setShowKey={setShowKey} submitting={submitting} />
                                                                                        <div className="input-sub-row">
                                                                                                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", paddingRight: "0.5rem" }}>{t.inputHint}</span>
                                                                                                <button type="button" onClick={() => setShowRequestModal(true)} className="support-link-btn" style={{ flexShrink: 0 }}>
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
                                        </div>
                                        <footer className="login-footer-bar">
                                                <div className="footer-encryption-status">
                                                        <Lock style={{ width: "0.75rem", height: "0.75rem" }} />
                                                        <span>{t.footerEncryption}</span>
                                                </div>
                                                <div>{t.footerVersion}</div>
                                        </footer>
                                </div>
                        </div>

                        <SupportModal t={t} showSupportModal={showSupportModal} setShowSupportModal={setShowSupportModal} />
                        <RequestAccessModal t={t} showRequestModal={showRequestModal} setShowRequestModal={setShowRequestModal} handleAutoFillTestKey={handleAutoFillTestKey} />
                </main>
        );
}
