/**
 * types.ts — Shared types for Login Variant components
 *
 * Single source of truth for the LoginVariantProps interface.
 * Eliminates the 3x interface duplication across VariantA/B/C.
 */

import type { FormEvent } from "react";

export interface LoginVariantProps {
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
