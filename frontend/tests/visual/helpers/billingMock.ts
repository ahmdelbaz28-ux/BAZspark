/**
 * billingMock.ts — Shared Playwright API mock helper for Meeza billing flow.
 *
 * Simulates the billing backend so E2E tests can run without a real FastAPI
 * backend. Mocks the full Meeza payment pipeline:
 *
 *   1. POST /api/v1/billing/orders → creates an order
 *   2. POST /api/v1/billing/orders/{id}/checkout → initiates checkout
 *   3. POST /api/v1/billing/webhooks/meeza → receives HMAC-verified webhook
 *   4. GET /api/v1/billing/orders/{id} → gets order status
 *   5. GET /api/v1/billing/orders/{id}/events → gets webhook audit trail
 *
 * The mock uses a per-page closure (via page.route()) to track state across
 * requests, similar to authMock.ts.
 */
import type { Page, Route } from "@playwright/test";

export type OrderStatus = "pending" | "processing" | "completed" | "failed";

export interface OrderEventRecord {
	id: string;
	status: string;
	txn_id: string | null;
}

export interface OrderRecord {
	id: string;
	amount_cents: number;
	currency: string;
	status: OrderStatus;
	created_at: string;
	events: OrderEventRecord[];
}

export interface BillingMockState {
	orders: Map<string, OrderRecord>;
	webhookDelivered: Map<string, boolean>;
	isAuthenticated?: boolean;
}

const createInitialOrder = (orderId: string, amountCents: number): OrderRecord => ({
	id: orderId,
	amount_cents: amountCents,
	currency: "EGP",
	status: "pending",
	created_at: new Date().toISOString(),
	events: [],
});

// Default state per page
let state: BillingMockState = {
	orders: new Map(),
	webhookDelivered: new Map(),
};

/**
 * Reset the mock state (useful between test groups).
 * Can be called from test setup or globally.
 */
export function resetBillingMockState() {
	state = {
		orders: new Map(),
		webhookDelivered: new Map(),
	};
}

/**
 * Get the current mock state for the page.
 */
export function getBillingMockState(): BillingMockState {
	return state;
}

/**
 * Fulfill a data endpoint with billing data.
 */
function fulfillBillingData(route: Route, method: string, override?: Record<string, unknown>) {
	const url = route.request().url();
	const isGet = method === "GET" || method === "HEAD";

	// If there's an order with this path pattern, return its data
	const orderIdMatch = method === "GET" && url.includes("/orders/")
		? (() => {
				try {
					const match = url.match(/\/orders\/([^?/]+)/);
					return match ? match[1] : null;
				} catch {
					return null;
				}
			})()
		: null;

	if (orderIdMatch && state.orders.has(orderIdMatch)) {
		const order = state.orders.get(orderIdMatch)!;
		return route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({
				success: true,
				data: {
					...order,
					...override,
				},
			}),
		});
	}

	// Default empty data for other GET requests
	return route.fulfill({
		status: 200,
		contentType: "application/json",
		body: JSON.stringify({
			success: true,
			data: isGet ? [] : {},
		}),
	});
}

export async function installBillingApiMock(page: Page) {
	// Initialize per-page state
	state = {
		orders: new Map(),
		webhookDelivered: new Map(),
		isAuthenticated: true,
	};

	await page.route("**/api/**", async (route: Route) => {
		const url = route.request().url();
		const method = route.request().method();

		// ── Health endpoint ─────────────────────────────────────
		if (url.includes("/api/health") || url.includes("/api/v1/health")) {
			return route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					success: true,
					data: {
						status: "ok",
						database: "connected",
						core_modules: "loaded",
					},
				}),
			});
		}

		// ── Auth endpoints (delegated to auth mock concept) ─────
		if (url.includes("/auth/me")) {
			// For billing tests, we'll pre-authenticate
			return route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					success: true,
					data: { role: "engineer" },
				}),
			});
		}

		if (url.includes("/auth/login") && method === "POST") {
			state.isAuthenticated = true;
			return route.fulfill({
				status: 200,
				contentType: "application/json",
				headers: { "Set-Cookie": "mock_session=engineer; Path=/; HttpOnly" },
				body: JSON.stringify({
					success: true,
					data: { role: "engineer" },
				}),
			});
		}

		if (url.includes("/auth/logout") && method === "POST") {
			state.isAuthenticated = false;
			return route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true }),
			});
		}

		// ── Billing: POST /api/v1/billing/orders ────────────────
		if (url.includes("/api/v1/billing/orders") && method === "POST") {
			try {
				const body = route.request().postDataJSON();
				const orderId = body?.order_id || body?.id || `order_${state.orders.size + 1}`;
				const order = createInitialOrder(orderId, body?.amount_cents ?? 50000);

				state.orders.set(orderId, {
					...order,
					events: [],
				});

				return route.fulfill({
					status: 201,
					contentType: "application/json",
					body: JSON.stringify({
						success: true,
						data: order,
					}),
				});
			} catch {
				return route.fulfill({
					status: 400,
					contentType: "application/json",
					body: JSON.stringify({
						success: false,
						detail: "Invalid request body",
					}),
				});
			}
		}

		// ── Billing: GET /api/v1/billing/orders ──────────────────
		if (url.includes("/api/v1/billing/orders") && method === "GET") {
			const userOrders = Array.from(state.orders.values());
			return route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					success: true,
					data: userOrders,
				}),
			});
		}

		// ── Billing: GET /api/v1/billing/orders/{id} ──────────────
		if (url.match(/\/api\/v1\/billing\/orders\/[^?/]+/) && method === "GET") {
			const orderIdMatch = url.match(/\/orders\/([^?/]+)/);
			const orderId = orderIdMatch?.[1];
			if (orderId && state.orders.has(orderId)) {
				const order = state.orders.get(orderId)!;
				return route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify({
						success: true,
						data: order,
					}),
				});
			}
			return route.fulfill({
				status: 404,
				contentType: "application/json",
				body: JSON.stringify({
					success: false,
					detail: "Order not found",
				}),
			});
		}

		// ── Billing: POST /api/v1/billing/orders/{id}/checkout ─────
		if (url.match(/\/api\/v1\/billing\/orders\/[^/]+\/checkout/) && method === "POST") {
			const orderIdMatch = url.match(/\/orders\/([^?/]+)/);
			const orderId = orderIdMatch?.[1];

			if (!orderId || !state.orders.has(orderId)) {
				return route.fulfill({
					status: 404,
					contentType: "application/json",
					body: JSON.stringify({
						success: false,
						detail: "Order not found",
					}),
				});
			}

			const order = state.orders.get(orderId)!;
			// Transition to processing
			order.status = "processing";

			return route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					success: true,
					data: {
						order_id: order.id,
						checkout_url: `https://accept.paymob.com/api/authorize?order_id=${order.id}`,
						method: "iframe",
						raw: { order_id: order.id, amount_cents: order.amount_cents },
					},
				}),
			});
		}

		// ── Billing: GET /api/v1/billing/orders/{id}/events ───────────
		if (url.match(/\/api\/v1\/billing\/orders\/[^/]+\/events/) && method === "GET") {
			const orderIdMatch = url.match(/\/orders\/([^?/]+)/);
			const orderId = orderIdMatch?.[1];
			if (orderId && state.orders.has(orderId)) {
				const order = state.orders.get(orderId)!;
				return route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify({
						success: true,
						data: order.events,
					}),
				});
			}
			return route.fulfill({
				status: 404,
				contentType: "application/json",
				body: JSON.stringify({
					success: false,
					detail: "Order not found",
				}),
			});
		}

		// ── Billing: POST /api/v1/billing/webhooks/meeza ──────────────
		if (url.includes("/api/v1/billing/webhooks/meeza") && method === "POST") {
			try {
				let body: Record<string, any> = {};
				try {
					body = route.request().postDataJSON() || {};
				} catch {
					body = {};
				}
				const signature = body?.signature ?? "";
				const orderId = body?.order_id ?? "";

				// Simple HMAC validation mock: accept if signature starts with "valid-"
				const isValid = typeof signature === "string" && signature.startsWith("valid-");

				if (!orderId) {
					return route.fulfill({
						status: 400,
						contentType: "application/json",
						body: JSON.stringify({
							success: false,
							detail: "Missing order_id",
						}),
					});
				}

				if (!state.orders.has(orderId)) {
					return route.fulfill({
						status: 200,
						contentType: "application/json",
						body: JSON.stringify({
							success: true,
							data: {
								status: "processed",
								http_status: 200,
								order_id: orderId,
								order_status: "completed",
								idempotency_key: `idx_${orderId}_${Date.now()}`,
								reason: "order_not_found_but_accepted",
							},
						}),
					});
				}

				const order = state.orders.get(orderId)!;

				if (!isValid) {
					return route.fulfill({
						status: 401,
						contentType: "application/json",
						body: JSON.stringify({
							success: false,
							detail: "Invalid webhook signature",
						}),
					});
				}

				// Check for duplicate (idempotency key or prior delivery)
				const isDuplicate =
					Boolean(state.webhookDelivered.get(orderId)) ||
					order.events.some(
						(e) => (body?.txn_id && e.txn_id === body?.txn_id) || e.status === "processed",
					);

				if (isDuplicate) {
					return route.fulfill({
						status: 200,
						contentType: "application/json",
						body: JSON.stringify({
							success: true,
							data: {
								status: "duplicate",
								http_status: 200,
								order_id: orderId,
								order_status: order.status,
								idempotency_key: `idx_${orderId}`,
								reason: "duplicate_delivery",
							},
						}),
					});
				}

				// Process the webhook - mark as completed
				const txnId = body?.txn_id || `txn_${Date.now()}`;
				order.events.push({
					id: `event_${Date.now()}`,
					status: "processed",
					txn_id: txnId,
				});

				// Status transition: mark as completed
				order.status = "completed";

				// Mark webhook as delivered for this order
				state.webhookDelivered.set(orderId, true);

				return route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify({
						success: true,
						data: {
							status: "processed",
							http_status: 200,
							order_id: orderId,
							order_status: order.status,
							idempotency_key: `idx_${orderId}_${txnId}`,
							reason: "successfully_processed",
						},
					}),
				});
			} catch {
				return route.fulfill({
					status: 500,
					contentType: "application/json",
					body: JSON.stringify({
						success: false,
						detail: "Internal server error",
					}),
				});
			}
		}

		// ── Default: data endpoints ────────────────────────────
		return fulfillBillingData(route, method);
	});

	// Mock Vercel scripts (same as authMock)
	await page.route("**/_vercel/insights/script.js", async (route) =>
		route.fulfill({ status: 204, contentType: "application/javascript", body: "" }),
	);
	await page.route("**/_vercel/speed-insights/script.js", async (route) =>
		route.fulfill({ status: 204, contentType: "application/javascript", body: "" }),
	);

	return {
		resetState: () => resetBillingMockState(),
		getState: () => getBillingMockState(),
		/** Create a new order via the mock API. */
		async createOrder(amountCents: number = 50000) {
			await page.request.post("/api/v1/billing/orders", {
				data: { amount_cents: amountCents },
			});
		},
		/** Initiate checkout for an order. */
		async initiateCheckout(orderId: string) {
			await page.request.post(`/api/v1/billing/orders/${orderId}/checkout`);
		},
		/** Submit a webhook for an order. */
		async submitWebhook(orderId: string, signature: string = "valid-sig-12345", txnId: string = `txn_${Date.now()}`) {
			await page.request.post("/api/v1/billing/webhooks/meeza", {
				data: { order_id: orderId, signature, txn_id: txnId },
			});
		},
		/** Get order status. */
		async getOrder(orderId: string) {
			const response = await page.request.get(`/api/v1/billing/orders/${orderId}`);
			return response.json();
		},
		/** Get order events. */
		async getEvents(orderId: string) {
			const response = await page.request.get(`/api/v1/billing/orders/${orderId}/events`);
			return response.json();
		},
	};
}