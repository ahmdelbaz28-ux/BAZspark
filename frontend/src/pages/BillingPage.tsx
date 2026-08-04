/**
 * frontend/src/pages/BillingPage.tsx
 * ==================================
 * Billing & Subscriptions page — wraps the MeezaPayment component with
 * page-level chrome (title, order-history teaser, security notes).
 */

import { MeezaPayment } from "../components/billing/MeezaPayment";

export function BillingPage() {
    return (
        <div className="min-h-screen bg-slate-50 py-8">
            <div className="max-w-5xl mx-auto px-4">
                <div className="mb-6">
                    <h1 className="text-2xl font-bold text-slate-900">Billing & Subscriptions</h1>
                    <p className="text-sm text-slate-600 mt-1">
                        Subscribe to BAZspark via Meeza national card. Card details are
                        handled by an Egyptian-licensed PSP — BAZspark never sees, stores,
                        or transmits your card number.
                    </p>
                </div>

                <MeezaPayment />

                <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-slate-500">
                    <div className="p-4 bg-white border border-slate-200 rounded-lg">
                        <h3 className="font-semibold text-slate-700 mb-1">HMAC-signed webhooks</h3>
                        <p>
                            Every payment callback is verified with HMAC/SHA-256 against a
                            server-side secret. Forged callbacks are rejected with 401.
                        </p>
                    </div>
                    <div className="p-4 bg-white border border-slate-200 rounded-lg">
                        <h3 className="font-semibold text-slate-700 mb-1">Idempotent processing</h3>
                        <p>
                            Duplicate webhook deliveries are detected by a derived
                            idempotency key and never re-fulfill an order. You will not be
                            double-charged.
                        </p>
                    </div>
                    <div className="p-4 bg-white border border-slate-200 rounded-lg">
                        <h3 className="font-semibold text-slate-700 mb-1">Atomic transitions</h3>
                        <p>
                            Order status changes are guarded by atomic SQL UPDATEs with a
                            <code className="px-1">status = 'pending'</code> filter — only
                            the first terminal webhook flips the order.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
