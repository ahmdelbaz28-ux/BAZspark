/**
 * LoginPage.tsx — BAZSPARK Login
 * ?variant=A|B|C switches between UI prototypes (A = current production design)
 */

import { type FormEvent, useCallback, useState } from "react";
import {
	Navigate as RouterNavigate,
	useSearchParams as useRouterSearchParams,
} from "react-router";
import { PrototypeSwitcher } from "@/components/ui/PrototypeSwitcher";
import { useAuth } from "@/contexts/AuthContext";
import { VariantA } from "@/pages/prototypes/login/VariantA";
import { VariantB } from "@/pages/prototypes/login/VariantB";
import { VariantC } from "@/pages/prototypes/login/VariantC";
import "@/styles/login.css";

// Multilingual Translation Dictionary for SCREEN_6
const translations = {
	en: {
		topBadge: "ENGINEERING INTELLIGENCE",
		heroTitle:
			"The World's Most Advanced AI-Powered Fire Safety Engineering Platform.",
		heroSubtitle:
			"From building complexes to maritime vessels, BAZspark automates compliance (NFPA 72, NEC, SOLAS) with precision intelligence.",
		feature1Title: "Automated CAD Design",
		feature1Desc: "Intelligent detector placement and optimal cable routing.",
		feature2Title: "Real-Time Compliance",
		feature2Desc:
			"Live safety rule engine tracking NFPA 72 & SOLAS 2024 standards.",
		feature3Title: "Digital Twin & BIM",
		feature3Desc:
			"High-fidelity 3D visualization and building information modeling.",
		feature4Title: "AI Engineering Agent",
		feature4Desc:
			"Proactive self-healing systems and predictive risk analysis.",
		feature5Title: "Marine SOLAS & IMO Compliance",
		feature5Desc:
			"Specialized fire safety for maritime vessels and offshore platforms.",
		formTitle: "Enter Your Engineering Workspace",
		formSubtitle: "Enter your engineering key to authenticate secure session.",
		inputLabel: "AUTHORIZATION KEY (API)",
		supportLink: "ENTERPRISE SUPPORT",
		inputPlaceholder: "BS-XXXX-XXXX-XXXX-XXXX",
		inputHint: "Required for terminal access and CAD synchronization.",
		requestAccessLink: "REQUEST ACCESS",
		rememberLabel: "Maintain persistent secure connection",
		submitButton: "INITIALIZE SECURE SESSION",
		submittingButton: "INITIALIZING SECURE SESSION...",
		footerEncryption: "AES-256 Encryption Active",
		footerVersion: "System Version 8.1 Production Ready",
		// Support Modal
		supportTitle: "Enterprise Support & Technical Assistance",
		supportDesc:
			"Need help acquiring an Engineering Key or connecting your Revit/AutoCAD workstation?",
		supportDocsBtn: "View API Key Documentation",
		supportEmail: "Direct Support: support@bazspark.com",
		closeBtn: "Close",
		// Request Access Modal
		requestTitle: "Request Engineering Access Key",
		requestDesc:
			"Engineering Keys are granted to certified life-safety designers, CAD operators, and enterprise partners.",
		autoFillDemoBtn: "Auto-Fill Valid Test Key (1-Click Demo)",
		accessGranted: "Access Granted",
		sessionInitialized: "Secure engineering session initialized successfully.",
		redirecting: "REDIRECTING TO DASHBOARD...",
	},
	ar: {
		topBadge: "الذكاء الهندسي المتقدم",
		heroTitle:
			"المنصة الأكثر تطوراً عالمياً للهندسة الوقائية والسلامة من الحرائق بالذكاء الاصطناعي.",
		heroSubtitle:
			"من المجمعات العمرانية إلى السفن البحرية، تمتلك BAZspark نظاماً آلياً لمطابقة الأكواد الدولية (NFPA 72, NEC, SOLAS) بدقة فائقة.",
		feature1Title: "التصميم الآلي لـ CAD",
		feature1Desc:
			"التوزيع الذكي لكواشف الحريق وتوجيه المسارات المثالية للكابلات.",
		feature2Title: "المطابقة في الوقت الفعلي",
		feature2Desc: "محرك قواعد سلامة حي يتبع معايير NFPA 72 و SOLAS 2024.",
		feature3Title: "التوأم الرقمي ونمذجة BIM",
		feature3Desc: "رؤية ثلاثية الأبعاد عالية الدقة ونمذجة معلومات المباني.",
		feature4Title: "وكيل الهندسة بالذكاء الاصطناعي",
		feature4Desc: "أنظمة المعالجة الذاتية التنبؤية وتحليل المخاطر الوقائي.",
		feature5Title: "مطابقة معايير المنظمة البحرية الدولية SOLAS & IMO",
		feature5Desc:
			"أنظمة حماية متخصصة للسفن البحرية والمنصات التابعة للقطاع البحري.",
		formTitle: "الدخول إلى مساحة العمل الهندسية",
		formSubtitle: "أدخل مفتاح الترخيص الهندسي للتحقق وبدء الجلسة الآمنة.",
		inputLabel: "مفتاح الترخيص (API)",
		supportLink: "الدعم الفني للمؤسسات",
		inputPlaceholder: "BS-XXXX-XXXX-XXXX-XXXX",
		inputHint: "مطلوب للوصول إلى وحدة التحكم وتزامن برامج CAD.",
		requestAccessLink: "طلب تصريح وصول",
		rememberLabel: "الحفاظ على اتصال آمن ومستمر",
		submitButton: "بدء الجلسة الآمنة",
		submittingButton: "جاري التحقق وبدء الجلسة...",
		footerEncryption: "تشفير AES-256 نشط",
		footerVersion: "إصدار النظام 8.1 جاهز للإنتاج",
		// Support Modal
		supportTitle: "الدعم الفني والمساعدة الهندسية",
		supportDesc:
			"هل تحتاج إلى مساعدة في الحصول على مفتاح ترخيص أو ربط محطة عمل Revit/AutoCAD؟",
		supportDocsBtn: "عرض دليل مفاتيح API",
		supportEmail: "الدعم المباشر: support@bazspark.com",
		closeBtn: "إغلاق",
		// Request Access Modal
		requestTitle: "طلب مفتاح ترخيص مهندسي",
		requestDesc:
			"يتم منح مفاتيح الترخيص للمهندسين المعتمدين والمشغلين والشركاء المؤسسيين.",
		autoFillDemoBtn: "تعبئة مفتاح تجريبي معتمد (بنقرة واحدة)",
		accessGranted: "تم منح تصريح الدخول",
		sessionInitialized: "تم بدء الجلسة الهندسية الآمنة بنجاح.",
		redirecting: "جاري التوجيه إلى لوحة التحكم...",
	},
};

/** Map login error messages to user-friendly localized text. */
function mapLoginError(msg: string, lang: "en" | "ar"): string {
	if (msg.includes("429") || msg.includes("Too many")) {
		return lang === "ar"
			? "محاولات كثيرة خاطئة. يرجى الانتظار بضع دقائق."
			: "Too many failed attempts. Please wait a few minutes.";
	}
	if (msg.includes("401") || msg.includes("Invalid")) {
		return lang === "ar"
			? "مفتاح الترخيص غير صحيح. يرجى التثبت والمحاولة مجدداً."
			: "Invalid Authorization key. Please verify and try again.";
	}
	if (msg.includes("Failed to fetch") || msg.includes("Network")) {
		return lang === "ar"
			? "تعذر الاتصال بالخادم. يرجى التحقق من اتصال الإنترنت."
			: "Unable to reach the server. Check your connection.";
	}
	return msg;
}

export function LoginPage() {
	const [searchParams] = useRouterSearchParams();
	const { isAuthenticated, loading: ctxLoading, login } = useAuth();

	// Language state (en | ar)
	const [lang, setLang] = useState<"en" | "ar">("en");
	const t = translations[lang];

	// Form state
	const [apiKey, setApiKey] = useState("");
	const [showKey, setShowKey] = useState(false);
	const [remember, setRemember] = useState(false);
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [isSuccess, setIsSuccess] = useState(false);
	const [redirectReady, setRedirectReady] = useState(false);

	// Modals state
	const [showSupportModal, setShowSupportModal] = useState(false);
	const [showRequestModal, setShowRequestModal] = useState(false);

	// Toggle language
	const toggleLanguage = () => {
		setLang((prev) => (prev === "en" ? "ar" : "en"));
	};

	// IMPORTANT: handleError must be declared BEFORE the early-return below so
	// hooks are called unconditionally on every render (react-hooks/rules-of-hooks).
	const handleError = useCallback(
		(err: unknown) => {
			const msg = err instanceof Error ? err.message : "Login failed";
			setError(mapLoginError(msg, lang));
		},
		[lang],
	);

	// Redirect if authenticated
	if (!ctxLoading && isAuthenticated && (redirectReady || !isSuccess)) {
		let from = searchParams.get("from") || "/dashboard";
		if (from && (from.startsWith("//") || !from.startsWith("/"))) {
			from = "/dashboard";
		}
		return <RouterNavigate to={from} replace />;
	}

	const handleSubmit = async (e: FormEvent) => {
		e.preventDefault();
		setError(null);

		if (!apiKey.trim()) {
			setError(
				lang === "ar"
					? "يرجى أدخال مفتاح الترخيص الخاص بك."
					: "Please enter your authorization key.",
			);
			return;
		}

		setSubmitting(true);
		try {
			if (remember) {
				try {
					sessionStorage.setItem(
						"fireai_remember",
						JSON.stringify({ remember: true }),
					);
				} catch {
					// sessionStorage might be restricted
				}
			}
			await login(apiKey.trim());
			setIsSuccess(true);
			setSubmitting(false);

			setTimeout(() => {
				setRedirectReady(true);
			}, 1400);
		} catch (err) {
			handleError(err);
			setSubmitting(false);
		}
	};

	// 1-Click Auto Fill Demo Key
	const handleAutoFillTestKey = () => {
		setApiKey("test-api-key-for-testing-only");
		setShowRequestModal(false);
		setError(null);
	};

	// Prototype variant switching
	const variant = searchParams.get("variant") ?? "A";
	const variantProps = {
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
	};

	return (
		<>
			{variant === "A" && <VariantA {...variantProps} />}
			{variant === "B" && <VariantB {...variantProps} />}
			{variant === "C" && <VariantC {...variantProps} />}
			<PrototypeSwitcher
				variants={[
					{ key: "A", label: "Engineering Terminal" },
					{ key: "B", label: "Minimal SaaS" },
					{ key: "C", label: "Dark Portal" },
				]}
			/>
		</>
	);
}
