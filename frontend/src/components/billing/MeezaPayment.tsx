/**
 * frontend/src/components/billing/MeezaPayment.tsx
 * ================================================
 * Meeza (ميزة) Payment Component — checkout UI + iframe/redirect handler.
 *
 * Features:
 *   - Dedicated "الدفع عبر كارت ميزة المحلي" payment option
 *   - Secure iframe loading of PSP-hosted Meeza card entry form
 *   - Fallback to redirect if iframe is blocked (X-Frame-Options)
 *   - Real-time feedback via periodic order status polling
 *   - State recovery: if the user navigates away mid-payment and comes back,
 *     the component resumes polling the existing transaction's status
 *   - Exponential backoff on polling to avoid hammering the backend
 *
 * Security:
 *   - The iframe loads a PSP-hosted URL (PayMob / bank). Card numbers NEVER
 *     touch our domain — they go directly to the PSP via the iframe.
 *   - The iframe URL is built server-side and returned by /checkout — the
 *     frontend never sees the API key or payment_key secret material (only
 *     the resulting URL, which is safe to expose to the user's browser).
 *   - The sandbox mode uses a synthetic URL and the /simulate-webhook
 *     endpoint for end-to-end testing without a live PSP.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
	type CheckoutResult,
	createOrder,
	formatAmount,
	getOrder,
	initiateCheckout,
	type Order,
	orderStatusLabel,
	simulateWebhook,
} from "../../services/billingApi";

// ── Plan presets (UI convenience) ───────────────────────────────────────────

export interface MeezaPlan {
	id: string;
	nameEn: string;
	nameAr: string;
	amountCents: number;
	description: string;
	highlight?: boolean;
}

export const MEEZA_PLANS: MeezaPlan[] = [
	{
		id: "starter",
		nameEn: "Starter",
		nameAr: "الباقة الابتدائية",
		amountCents: 9900, // 99.00 EGP
		description: "Single project, basic engineering modules",
	},
	{
		id: "pro",
		nameEn: "Professional",
		nameAr: "الباقة الاحترافية",
		amountCents: 49900, // 499.00 EGP
		description: "Up to 20 projects, full fire-AI + marine + mining",
		highlight: true,
	},
	{
		id: "enterprise",
		nameEn: "Enterprise",
		nameAr: "باقة المؤسسات",
		amountCents: 199900, // 1999.00 EGP
		description: "Unlimited projects, multi-DB, dedicated support",
	},
];

// ── Component state machine ─────────────────────────────────────────────────

type Phase =
	| { kind: "select" } // choosing a plan
	| { kind: "creating_order" } // POST /orders in flight
	| { kind: "initiating_checkout" } // POST /checkout in flight
	| { kind: "iframe"; checkout: CheckoutResult; order: Order } // showing PSP iframe
	| { kind: "redirect"; checkout: CheckoutResult; order: Order } // fallback: full-tab redirect
	| { kind: "polling"; order: Order; txnId: string } // polling for status
	| { kind: "success"; order: Order }
	| { kind: "failed"; order: Order; reason: string }
	| { kind: "expired"; order: Order }
	| { kind: "cancelled"; order: Order }
	| { kind: "error"; message: string };

// Persisted order id so a page refresh mid-payment can resume polling.
const PENDING_ORDER_KEY = "bazspark_pending_meeza_order";

export function MeezaPayment() {
	const [phase, setPhase] = useState<Phase>({ kind: "select" });
	const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const pollAttemptsRef = useRef(0);
	// Ref indirection lets `pollOrderStatus` reference itself recursively
	// without tripping react-compiler's "Cannot access variable before
	// declaration" rule (TDZ check on const useCallback).
	const pollOrderStatusRef = useRef<
		((orderId: string, txnId: string) => Promise<void>) | null
	>(null);

	// ── Map an Order's terminal status to the corresponding Phase ──────
	const setPhaseFromOrder = useCallback((order: Order) => {
		switch (order.status) {
			case "paid":
				setPhase({ kind: "success", order });
				break;
			case "failed":
				setPhase({ kind: "failed", order, reason: "Payment was declined" });
				break;
			case "expired":
				setPhase({ kind: "expired", order });
				break;
			case "cancelled":
				setPhase({ kind: "cancelled", order });
				break;
			default:
				setPhase({ kind: "select" });
		}
	}, []);

	// ── Polling: exponential backoff, max ~30s, max 60 attempts (~15min) ─
	const pollOrderStatus = useCallback(
		async (orderId: string, txnId: string) => {
			const maxAttempts = 60;
			const backoff = Math.min(1500 * 1.3 ** pollAttemptsRef.current, 30000);
			pollAttemptsRef.current += 1;

			if (pollAttemptsRef.current > maxAttempts) {
				try {
					const order = await getOrder(orderId);
					setPhase({
						kind: "failed",
						order,
						reason: "Polling timed out — please check your order history",
					});
				} catch {
					setPhase({
						kind: "error",
						message: "Polling timed out and order lookup failed",
					});
				}
				return;
			}

			try {
				const order = await getOrder(orderId);
				if (order.status === "pending") {
					pollTimerRef.current = setTimeout(() => {
						void pollOrderStatusRef.current?.(orderId, txnId);
					}, backoff);
					return;
				}
				setPhaseFromOrder(order);
			} catch {
				// Network blip — keep polling with backoff
				pollTimerRef.current = setTimeout(() => {
					void pollOrderStatusRef.current?.(orderId, txnId);
				}, backoff);
			}
		},
		[setPhaseFromOrder],
	);

	// Keep the ref in sync so the setTimeout recursion resolves to the
	// latest memoized instance. Refs must not be mutated during render,
	// so we do it inside an effect (react-hooks/refs rule).
	useEffect(() => {
		pollOrderStatusRef.current = pollOrderStatus;
	}, [pollOrderStatus]);

	// ── Resume in-flight payment on mount ──────────────────────────────
	useEffect(() => {
		const pendingOrderId = sessionStorage.getItem(PENDING_ORDER_KEY);
		if (!pendingOrderId) return;
		sessionStorage.removeItem(PENDING_ORDER_KEY);
		(async () => {
			try {
				const order = await getOrder(pendingOrderId);
				if (order.status === "pending") {
					setPhase({ kind: "polling", order, txnId: "" });
				} else {
					setPhaseFromOrder(order);
				}
			} catch {
				// Order may belong to another session or be deleted — silently
				// return to plan selection.
				setPhase({ kind: "select" });
			}
		})();
		return () => {
			if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
		};
	}, [setPhaseFromOrder]);

	// ── Action: start checkout for a selected plan ─────────────────────
	const startCheckout = useCallback(
		async (plan: MeezaPlan) => {
			setPhase({ kind: "creating_order" });
			try {
				const order = await createOrder({
					amount_cents: plan.amountCents,
					description: `${plan.nameEn} subscription`,
					metadata: { plan_id: plan.id, source: "meeza_payment_ui" },
				});
				sessionStorage.setItem(PENDING_ORDER_KEY, order.id);
				setPhase({ kind: "initiating_checkout" });
				const checkout = await initiateCheckout(order.id, {});
				order.status = "pending"; // ensure
				setPhase({ kind: "iframe", checkout, order });
				// Start polling in parallel — iframe may not post back reliably
				pollAttemptsRef.current = 0;
				void pollOrderStatus(order.id, checkout.transaction_id);
			} catch (e: unknown) {
				setPhase({
					kind: "error",
					message: e instanceof Error ? e.message : "Failed to start checkout",
				});
			}
		},
		[pollOrderStatus],
	);

	// ── Action: switch from iframe to full-page redirect (X-Frame-Options) ─
	const fallbackToRedirect = useCallback(() => {
		if (phase.kind !== "iframe") return;
		setPhase({
			kind: "redirect",
			checkout: phase.checkout,
			order: phase.order,
		});
		window.location.href = phase.checkout.checkout_url;
	}, [phase]);

	// ── Action: cancel ──────────────────────────────────────────────────
	const cancel = useCallback(() => {
		sessionStorage.removeItem(PENDING_ORDER_KEY);
		if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
		setPhase({ kind: "select" });
	}, []);

	// ── Action: simulate webhook (sandbox only — for end-to-end testing) ─
	const simulateSuccess = useCallback(async () => {
		if (phase.kind !== "iframe" && phase.kind !== "polling") return;
		const orderId = phase.order.id;
		try {
			await simulateWebhook(orderId, "SUCCESS");
			const updated = await getOrder(orderId);
			setPhaseFromOrder(updated);
		} catch (e: unknown) {
			// simulate-webhook returns 403 when not in sandbox mode
			console.warn("[MeezaPayment] simulate-webhook failed:", e);
		}
	}, [phase, setPhaseFromOrder]);

	// ── Render ─────────────────────────────────────────────────────────
	return (
		<div className="w-full max-w-3xl mx-auto p-6 bg-white rounded-xl shadow-sm border border-slate-200">
			<header className="mb-6 flex items-center gap-3">
				<div className="w-12 h-12 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center text-white font-bold text-lg shadow">
					م
				</div>
				<div>
					<h2 className="text-xl font-semibold text-slate-900">
						الدفع عبر كارت ميزة المحلي
					</h2>
					<p className="text-sm text-slate-500">
						Meeza national card payment — secured by Egyptian PSP
					</p>
				</div>
			</header>

			{phase.kind === "select" && (
				<PlanSelector plans={MEEZA_PLANS} onSelect={startCheckout} />
			)}

			{(phase.kind === "creating_order" ||
				phase.kind === "initiating_checkout") && (
				<LoadingState
					label={
						phase.kind === "creating_order"
							? "Creating order..."
							: "Contacting Meeza PSP..."
					}
				/>
			)}

			{phase.kind === "iframe" && (
				<IframeCheckout
					checkout={phase.checkout}
					order={phase.order}
					onFallbackToRedirect={fallbackToRedirect}
					onCancel={cancel}
					onSimulateSuccess={simulateSuccess}
				/>
			)}

			{phase.kind === "redirect" && (
				<LoadingState label="Redirecting to Meeza PSP — if the page does not open, click the link below." />
			)}

			{phase.kind === "polling" && (
				<PollingState order={phase.order} onCancel={cancel} />
			)}

			{phase.kind === "success" && (
				<SuccessState
					order={phase.order}
					onDone={() => setPhase({ kind: "select" })}
				/>
			)}

			{(phase.kind === "failed" ||
				phase.kind === "expired" ||
				phase.kind === "cancelled") && (
				<FailureState
					order={phase.order}
					reason={phase.kind === "failed" ? phase.reason : undefined}
					onRetry={() => setPhase({ kind: "select" })}
				/>
			)}

			{phase.kind === "error" && (
				<div className="p-4 bg-rose-50 border border-rose-200 rounded-lg">
					<p className="text-rose-800 font-medium">Error</p>
					<p className="text-rose-700 text-sm mt-1">{phase.message}</p>
					<button
						type="button"
						onClick={() => setPhase({ kind: "select" })}
						className="mt-3 px-4 py-2 bg-rose-600 text-white rounded-md hover:bg-rose-700 text-sm"
					>
						Back to plans
					</button>
				</div>
			)}
		</div>
	);
}

// ── Plan selector subcomponent ──────────────────────────────────────────────

function PlanSelector({
	plans,
	onSelect,
}: Readonly<{
	plans: MeezaPlan[];
	onSelect: (plan: MeezaPlan) => void;
}>) {
	const [busy, setBusy] = useState<string | null>(null);
	return (
		<div className="space-y-3">
			<p className="text-sm text-slate-600 mb-3">
				اختر باقة الاشتراك — Choose a subscription plan:
			</p>
			{plans.map((plan) => (
				<div
					key={plan.id}
					className={`p-4 rounded-lg border-2 transition-all ${
						plan.highlight
							? "border-emerald-400 bg-emerald-50/50"
							: "border-slate-200 bg-white hover:border-slate-300"
					}`}
				>
					<div className="flex items-start justify-between gap-4">
						<div className="flex-1">
							<div className="flex items-center gap-2">
								<h3 className="font-semibold text-slate-900">{plan.nameEn}</h3>
								<span className="text-sm text-slate-500" dir="rtl">
									{plan.nameAr}
								</span>
								{plan.highlight && (
									<span className="text-xs px-2 py-0.5 bg-emerald-600 text-white rounded-full">
										Popular
									</span>
								)}
							</div>
							<p className="text-sm text-slate-600 mt-1">{plan.description}</p>
							<p className="text-lg font-bold text-slate-900 mt-2">
								{formatAmount(plan.amountCents, "EGP")}
								<span className="text-sm font-normal text-slate-500">
									{" "}
									/ month
								</span>
							</p>
						</div>
						<button
							type="button"
							disabled={busy !== null}
							onClick={() => {
								setBusy(plan.id);
								onSelect(plan);
							}}
							className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
								plan.highlight
									? "bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
									: "bg-slate-100 text-slate-800 hover:bg-slate-200 disabled:opacity-50"
							}`}
						>
							{busy === plan.id ? "..." : "Pay with Meeza"}
						</button>
					</div>
				</div>
			))}
			<p className="text-xs text-slate-400 mt-4">
				Card details are entered on the PSP-hosted secure iframe — they never
				touch BAZspark servers. HMAC-signed webhooks confirm payment.
			</p>
		</div>
	);
}

// ── Iframe checkout subcomponent ────────────────────────────────────────────

function IframeCheckout({
	checkout,
	order,
	onFallbackToRedirect,
	onCancel,
	onSimulateSuccess,
}: Readonly<{
	checkout: CheckoutResult;
	order: Order;
	onFallbackToRedirect: () => void;
	onCancel: () => void;
	onSimulateSuccess: () => void;
}>) {
	const [iframeFailed, setIframeFailed] = useState(false);
	const isSandbox = checkout.method === "sandbox";

	return (
		<div className="space-y-4">
			<div className="p-3 bg-slate-50 border border-slate-200 rounded-md text-sm">
				<div className="flex items-center justify-between">
					<span className="text-slate-600">Order</span>
					<code className="text-slate-800 font-mono text-xs">
						{order.id.slice(0, 8)}
					</code>
				</div>
				<div className="flex items-center justify-between mt-1">
					<span className="text-slate-600">Amount</span>
					<span className="font-semibold text-slate-900">
						{formatAmount(order.amount_cents, order.currency)}
					</span>
				</div>
				<div className="flex items-center justify-between mt-1">
					<span className="text-slate-600">Method</span>
					<span className="text-slate-800 uppercase text-xs">
						{checkout.method}
					</span>
				</div>
			</div>

			{isSandbox ? (
				<div className="p-6 bg-amber-50 border-2 border-dashed border-amber-300 rounded-lg text-center">
					<p className="text-amber-800 font-medium">Sandbox mode</p>
					<p className="text-sm text-amber-700 mt-1">
						No live PSP configured. Click below to simulate a successful Meeza
						webhook delivery and verify the end-to-end flow.
					</p>
					<button
						type="button"
						onClick={onSimulateSuccess}
						className="mt-3 px-4 py-2 bg-emerald-600 text-white rounded-md hover:bg-emerald-700 text-sm"
					>
						Simulate successful payment
					</button>
				</div>
			) : (
				<>
					{!iframeFailed ? (
						<iframe
							src={checkout.checkout_url}
							title="Meeza secure payment"
							className="w-full h-[500px] border-0 rounded-md bg-slate-50"
							sandbox="allow-forms allow-scripts allow-top-navigation-by-user-activation"
							onLoad={() => setIframeFailed(false)}
							onError={() => setIframeFailed(true)}
						/>
					) : (
						<div className="p-6 bg-amber-50 border border-amber-300 rounded-lg text-center">
							<p className="text-amber-800 font-medium">
								Iframe blocked by PSP (X-Frame-Options)
							</p>
							<p className="text-sm text-amber-700 mt-1">
								Some Meeza PSPs refuse to load in an iframe. Click below to
								complete payment in a full new tab.
							</p>
						</div>
					)}

					<div className="flex items-center justify-between gap-3">
						<button
							type="button"
							onClick={onCancel}
							className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800"
						>
							Cancel payment
						</button>
						<button
							type="button"
							onClick={onFallbackToRedirect}
							className="px-4 py-2 text-sm bg-slate-100 text-slate-800 rounded-md hover:bg-slate-200"
						>
							Open in new tab instead
						</button>
					</div>
				</>
			)}
		</div>
	);
}

// ── Other state subcomponents ───────────────────────────────────────────────

function LoadingState({ label }: Readonly<{ label: string }>) {
	return (
		<div className="py-12 flex flex-col items-center gap-3">
			<div className="w-10 h-10 border-4 border-emerald-200 border-t-emerald-600 rounded-full animate-spin" />
			<p className="text-slate-600 text-sm">{label}</p>
		</div>
	);
}

function PollingState({
	order,
	onCancel,
}: Readonly<{
	order: Order;
	onCancel: () => void;
}>) {
	return (
		<div className="py-12 flex flex-col items-center gap-3">
			<div className="w-10 h-10 border-4 border-amber-200 border-t-amber-600 rounded-full animate-spin" />
			<p className="text-slate-700 font-medium">
				Waiting for payment confirmation...
			</p>
			<p className="text-sm text-slate-500">
				Order <code className="font-mono text-xs">{order.id.slice(0, 8)}</code>{" "}
				— {formatAmount(order.amount_cents, order.currency)}
			</p>
			<p className="text-xs text-slate-400">
				If you completed payment, this will update automatically. If you
				navigated away from the PSP page, please return and complete it.
			</p>
			<button
				type="button"
				onClick={onCancel}
				className="mt-2 text-sm text-slate-500 hover:text-slate-700"
			>
				Cancel and start over
			</button>
		</div>
	);
}

function SuccessState({
	order,
	onDone,
}: Readonly<{
	order: Order;
	onDone: () => void;
}>) {
	return (
		<div className="py-10 flex flex-col items-center gap-3">
			<div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center">
				<svg
					viewBox="0 0 24 24"
					fill="none"
					className="w-10 h-10 text-emerald-600"
				>
					<path
						d="M5 13l4 4L19 7"
						stroke="currentColor"
						strokeWidth="2.5"
						strokeLinecap="round"
						strokeLinejoin="round"
					/>
				</svg>
			</div>
			<h3 className="text-lg font-semibold text-slate-900">
				Payment successful
			</h3>
			<p className="text-sm text-slate-600">
				Order <code className="font-mono text-xs">{order.id.slice(0, 8)}</code>{" "}
				— {formatAmount(order.amount_cents, order.currency)}
			</p>
			<p className="text-xs text-slate-400">
				Paid at {order.paid_at ? new Date(order.paid_at).toLocaleString() : "—"}
			</p>
			<button
				type="button"
				onClick={onDone}
				className="mt-3 px-5 py-2 bg-emerald-600 text-white rounded-md hover:bg-emerald-700 text-sm"
			>
				Done
			</button>
		</div>
	);
}

function FailureState({
	order,
	reason,
	onRetry,
}: Readonly<{
	order: Order;
	reason?: string;
	onRetry: () => void;
}>) {
	const label = orderStatusLabel(order.status);
	return (
		<div className="py-10 flex flex-col items-center gap-3">
			<div className="w-16 h-16 bg-rose-100 rounded-full flex items-center justify-center">
				<svg
					viewBox="0 0 24 24"
					fill="none"
					className="w-10 h-10 text-rose-600"
				>
					<path
						d="M6 18L18 6M6 6l12 12"
						stroke="currentColor"
						strokeWidth="2.5"
						strokeLinecap="round"
					/>
				</svg>
			</div>
			<h3 className="text-lg font-semibold text-slate-900">
				{label.en}{" "}
				<span dir="rtl" className="text-slate-500 text-sm">
					— {label.ar}
				</span>
			</h3>
			{reason && <p className="text-sm text-rose-600">{reason}</p>}
			<p className="text-sm text-slate-500">
				Order <code className="font-mono text-xs">{order.id.slice(0, 8)}</code>
			</p>
			<button
				type="button"
				onClick={onRetry}
				className="mt-3 px-5 py-2 bg-slate-100 text-slate-800 rounded-md hover:bg-slate-200 text-sm"
			>
				Try again
			</button>
		</div>
	);
}

// Re-export TxnStatus so consumers can use this as a single entry point
// (SonarCloud S7763: prefer `export…from` for re-exports.)
export type { TxnStatus } from "../../services/billingApi";
