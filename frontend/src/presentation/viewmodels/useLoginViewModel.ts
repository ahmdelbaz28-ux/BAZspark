/**
 * useLoginViewModel.ts — ViewModel for LoginPage.
 * Implements MVVM Architecture (Presentation Layer ViewModel).
 * Encapsulates form state, language selection, authorization handling, and modal triggers.
 */

import { useState, FormEvent } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { authRepository } from "../../data/repositories/AuthRepository";

export interface LoginViewModelOptions {
	onSuccessRedirect?: () => void;
}

export function useLoginViewModel(options: LoginViewModelOptions = {}) {
	const { isAuthenticated, loading: ctxLoading, login: authLoginContext } = useAuth();

	// Language State
	const [lang, setLang] = useState<"en" | "ar">("en");

	// Input & Form State
	const [apiKey, setApiKey] = useState("");
	const [showKey, setShowKey] = useState(false);
	const [remember, setRemember] = useState(false);
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [isSuccess, setIsSuccess] = useState(false);
	const [redirectReady, setRedirectReady] = useState(false);

	// Modals State
	const [showSupportModal, setShowSupportModal] = useState(false);
	const [showRequestModal, setShowRequestModal] = useState(false);

	const toggleLanguage = () => {
		setLang((prev) => (prev === "en" ? "ar" : "en"));
	};

	const handleError = (err: unknown) => {
		const msg = err instanceof Error ? err.message : "Login failed";
		if (msg.includes("429") || msg.includes("Too many")) {
			setError(lang === "ar" ? "محاولات كثيرة خاطئة. يرجى الانتظار بضع دقائق." : "Too many failed attempts. Please wait a few minutes.");
		} else if (msg.includes("401") || msg.includes("Invalid")) {
			setError(lang === "ar" ? "مفتاح الترخيص غير صحيح. يرجى التثبت والمحاولة مجدداً." : "Invalid Authorization key. Please verify and try again.");
		} else if (msg.includes("Failed to fetch") || msg.includes("Network")) {
			setError(lang === "ar" ? "تعذر الاتصال بالخادم. يرجى التحقق من اتصال الإنترنت." : "Unable to reach the server. Check your connection.");
		} else {
			setError(msg);
		}
	};

	const handleSubmit = async (e: FormEvent) => {
		e.preventDefault();
		if (!apiKey.trim()) {
			setError(lang === "ar" ? "يرجى إدخال مفتاح الترخيص الهندسي." : "Please enter your engineering authorization key.");
			return;
		}

		setSubmitting(true);
		setError(null);

		try {
			// First attempt using domain AuthRepository
			const repoRes = await authRepository.login({ username: apiKey, password: apiKey });
			
			// Auth Context login delegate
			await authLoginContext(apiKey);
			setIsSuccess(true);
			setTimeout(() => {
				setRedirectReady(true);
				options.onSuccessRedirect?.();
			}, 800);
		} catch (err) {
			handleError(err);
		} finally {
			setSubmitting(false);
		}
	};

	return {
		lang,
		setLang,
		toggleLanguage,
		apiKey,
		setApiKey,
		showKey,
		setShowKey,
		remember,
		setRemember,
		submitting,
		error,
		setError,
		isSuccess,
		redirectReady,
		showSupportModal,
		setShowSupportModal,
		showRequestModal,
		setShowRequestModal,
		ctxLoading,
		isAuthenticated,
		handleSubmit,
	};
}
