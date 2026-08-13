/**
 * frontend/src/services/billingApi.ts
 * ===================================
 * Meeza (ميزة) Payment Gateway API client.
 *
 * Wraps all /api/v1/billing endpoints exposed by backend/routers/billing.py.
 * Uses the shared ApiClient for auth + CSRF + retry.
 *
 * Endpoints:
 *   POST /orders                              — create a new billing order
 *   GET  /orders                              — list caller's orders
 *   GET  /orders/{order_id}                   — get a single order
 *   POST /orders/{order_id}/checkout          — initiate Meeza checkout
 *   GET  /orders/{order_id}/transactions      — list transactions for order
 *   GET  /orders/{order_id}/events            — webhook audit trail (admin)
 *   GET  /transactions/{txn_id}               — get a transaction (admin)
 *   POST /orders/{order_id}/simulate-webhook  — sandbox-only test endpoint
 *   POST /webhooks/meeza                      — Meeza PSP webhook (server-side)
 */

import { apiCall } from "./fullApi";

// ── Types ────────────────────────────────────────────────────────────────────

export type OrderStatus =
	| "pending"
	| "paid"
	| "failed"
	| "expired"
	| "cancelled"
	| "refunded";

export type TxnStatus =
	| "PENDING"
	| "SUCCESS"
	| "FAILED"
	| "EXPIRED"
	| "CANCELLED";

export type CheckoutMethod = "iframe" | "redirect" | "sandbox";

export interface Order {
	id: string;
	user_principal: string;
	amount_cents: number;
	currency: string;
	status: OrderStatus;
	description: string;
	metadata: Record<string, unknown>;
	created_at: string;
	updated_at: string;
	expires_at: string | null;
	paid_at: string | null;
}

export interface CheckoutResult {
	order_id: string;
	transaction_id: string;
	checkout_url: string;
	method: CheckoutMethod;
	raw: Record<string, unknown>;
}

export interface PaymentTransaction {
	id: string;
	order_id: string;
	psp_name: string;
	psp_order_id: string | null;
	psp_payment_key: string | null;
	psp_txn_id: string | null;
	amount_cents: number;
	currency: string;
	status: TxnStatus;
	idempotency_key: string;
	raw_payload: Record<string, unknown>;
	hmac_signature: string | null;
	created_at: string;
	updated_at: string;
	completed_at: string | null;
}

export interface PaymentEvent {
	id: string;
	transaction_id: string | null;
	order_id: string;
	event_type: string;
	psp_name: string;
	idempotency_key: string;
	raw_payload: Record<string, unknown> | string;
	hmac_signature: string | null;
	processed_at: string;
	response_code: number;
}

export interface CreateOrderRequest {
	amount_cents: number;
	currency?: string;
	description?: string;
	metadata?: Record<string, unknown>;
	expires_in_seconds?: number;
}

export interface CheckoutRequest {
	billing_data?: {
		email?: string;
		first_name?: string;
		last_name?: string;
		phone?: string;
		city?: string;
	};
}

// ── API functions ───────────────────────────────────────────────────────────

export async function createOrder(body: CreateOrderRequest): Promise<Order> {
	return apiCall<Order>("/billing/orders", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	});
}

export async function listOrders(params?: {
	limit?: number;
	offset?: number;
	status_filter?: OrderStatus;
}): Promise<Order[]> {
	const search = new URLSearchParams();
	if (params?.limit !== undefined) search.set("limit", String(params.limit));
	if (params?.offset !== undefined) search.set("offset", String(params.offset));
	if (params?.status_filter) search.set("status_filter", params.status_filter);
	const query = search.toString();
	return apiCall<Order[]>(`/billing/orders${query ? "?" + query : ""}`, {
		method: "GET",
	});
}

export async function getOrder(orderId: string): Promise<Order> {
	return apiCall<Order>(`/billing/orders/${encodeURIComponent(orderId)}`, {
		method: "GET",
	});
}

export async function initiateCheckout(
	orderId: string,
	body: CheckoutRequest = {},
): Promise<CheckoutResult> {
	return apiCall<CheckoutResult>(
		`/billing/orders/${encodeURIComponent(orderId)}/checkout`,
		{
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(body),
		},
	);
}

export async function listTransactionsForOrder(
	orderId: string,
): Promise<PaymentTransaction[]> {
	return apiCall<PaymentTransaction[]>(
		`/billing/orders/${encodeURIComponent(orderId)}/transactions`,
		{ method: "GET" },
	);
}

export async function listEventsForOrder(
	orderId: string,
): Promise<PaymentEvent[]> {
	return apiCall<PaymentEvent[]>(
		`/billing/orders/${encodeURIComponent(orderId)}/events`,
		{ method: "GET" },
	);
}

export async function getTransaction(
	txnId: string,
): Promise<PaymentTransaction> {
	return apiCall<PaymentTransaction>(
		`/billing/transactions/${encodeURIComponent(txnId)}`,
		{
			method: "GET",
		},
	);
}

/**
 * [SANDBOX ONLY] Simulate a Meeza webhook delivery for an order.
 * Drives the full HMAC + idempotency + atomic-transition pipeline
 * without a live PSP. Returns 403 when MEEZA_PSP_PROVIDER != sandbox.
 */
export async function simulateWebhook(
	orderId: string,
	txnStatus: TxnStatus = "SUCCESS",
): Promise<{
	status: "processed" | "duplicate" | "rejected";
	http_status: number;
	order_id?: string;
	transaction_status?: TxnStatus;
	order_status?: OrderStatus;
	idempotency_key?: string;
	reason?: string;
}> {
	return apiCall(
		`/billing/orders/${encodeURIComponent(orderId)}/simulate-webhook?txn_status=${encodeURIComponent(
			txnStatus,
		)}`,
		{ method: "POST" },
	);
}

// ── Helpers ─────────────────────────────────────────────────────────────────

/** Format an amount in smallest-currency-unit (piastres) as a human-readable
 * currency string. 50000 → "EGP 500.00". */
export function formatAmount(amountCents: number, currency = "EGP"): string {
	const major = amountCents / 100;
	return `${currency} ${major.toFixed(2)}`;
}

/** Map a backend OrderStatus to a human-readable Arabic/English label. */
export function orderStatusLabel(status: OrderStatus): {
	en: string;
	ar: string;
} {
	const labels: Record<OrderStatus, { en: string; ar: string }> = {
		pending: { en: "Pending", ar: "قيد الانتظار" },
		paid: { en: "Paid", ar: "مدفوع" },
		failed: { en: "Failed", ar: "فشل" },
		expired: { en: "Expired", ar: "منتهي" },
		cancelled: { en: "Cancelled", ar: "ملغي" },
		refunded: { en: "Refunded", ar: "مُسترد" },
	};
	return labels[status] ?? { en: status, ar: status };
}

/** Map a backend TxnStatus to a tailwind-friendly color class for badges. */
export function txnStatusColor(status: TxnStatus): string {
	switch (status) {
		case "SUCCESS":
			return "bg-emerald-100 text-emerald-800 border-emerald-300";
		case "PENDING":
			return "bg-amber-100 text-amber-800 border-amber-300";
		case "FAILED":
		case "CANCELLED":
			return "bg-rose-100 text-rose-800 border-rose-300";
		case "EXPIRED":
			return "bg-slate-100 text-slate-800 border-slate-300";
		default:
			return "bg-gray-100 text-gray-800 border-gray-300";
	}
}
