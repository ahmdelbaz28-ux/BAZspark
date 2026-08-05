import React, { useState } from "react";
import { CreditCard, CheckCircle2, AlertCircle, Loader2, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface MeezaPaymentModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  amountEgp?: number;
  planName?: string;
}

export function MeezaPaymentModal({
  open,
  onOpenChange,
  amountEgp = 499,
  planName = "الخطة الاحترافية (Professional Plan)",
}: MeezaPaymentModalProps) {
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(false);
  const [paymentData, setPaymentData] = useState<{
    payment_id: string;
    redirect_url: string;
    iframe_url: string;
  } | null>(null);
  const [status, setStatus] = useState<"IDLE" | "INITIATED" | "SUCCESS" | "FAILED">("IDLE");
  const [errorMsg, setErrorMsg] = useState("");

  const handleInitiate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      setErrorMsg("يرجى إدخال البريد الإلكتروني (Email is required)");
      return;
    }
    setLoading(true);
    setErrorMsg("");

    try {
      const apiUrl = import.meta.env.VITE_API_URL || "/api/v1";
      const res = await fetch(`${apiUrl}/billing/meeza/initiate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          amount: amountEgp,
          currency: "EGP",
          description: planName,
          customer_email: email,
          customer_phone: phone || undefined,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "فشل إنشاء جلسة الدفع عبر ميزة");
      }

      const data = await res.json();
      setPaymentData({
        payment_id: data.payment_id,
        redirect_url: data.redirect_url,
        iframe_url: data.iframe_url,
      });
      setStatus("INITIATED");
    } catch (err: unknown) {
      setErrorMsg((err as Error).message);
      setStatus("FAILED");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md dir-rtl text_right">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            <CreditCard className="h-6 w-6 text-emerald-600" />
            الدفع عبر كارت ميزة المحلي (Meeza)
          </DialogTitle>
          <DialogDescription>
            شبكة ميزة القومية للمدفوعات — الدفع المباشر بالجنيه المصري (EGP)
          </DialogDescription>
        </DialogHeader>

        {status === "IDLE" && (
          <form onSubmit={handleInitiate} className="space-y-4 py-2">
            <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/40 p-3 border border-emerald-200 dark:border-emerald-800 text-sm">
              <div className="flex justify-between font-semibold text-emerald-900 dark:text-emerald-200">
                <span>المبلغ المطلوب:</span>
                <span>{amountEgp} ج.م</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">{planName}</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="meeza-email">البريد الإلكتروني *</Label>
              <Input
                id="meeza-email"
                type="email"
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="meeza-phone">رقم الموبايل (اختياري)</Label>
              <Input
                id="meeza-phone"
                type="tel"
                placeholder="01012345678"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </div>

            {errorMsg && (
              <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 p-2 rounded">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            <Button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold" disabled={loading}>
              {loading ? <Loader2 className="animate-spin h-4 w-4 ml-2" /> : null}
              تأكيد وبدء الدفع عبر كارت ميزة
            </Button>
          </form>
        )}

        {status === "INITIATED" && paymentData && (
          <div className="space-y-4 py-3 text-center">
            <div className="flex justify-center">
              <CheckCircle2 className="h-12 w-12 text-emerald-500" />
            </div>
            <h3 className="font-semibold text-lg">تم تجهيز بوابة ميزة للدفع</h3>
            <p className="text-sm text-muted-foreground">
              معرف المعاملة: <code className="bg-muted px-1 py-0.5 rounded text-xs">{paymentData.payment_id}</code>
            </p>

            <div className="pt-2 space-y-2">
              <a
                href={paymentData.redirect_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-md bg-emerald-600 text-white font-semibold hover:bg-emerald-700 transition-colors"
              >
                انتقال إلى صفحة الدفع الآمنة (Meeza Gateway)
                <ExternalLink className="h-4 w-4" />
              </a>

              <Button variant="outline" className="w-full" onClick={() => onOpenChange(false)}>
                إغلاق النافذة (متابعة الدفع في التبويب الجديد)
              </Button>
            </div>
          </div>
        )}

        {status === "FAILED" && (
          <div className="space-y-4 py-3 text-center">
            <AlertCircle className="h-12 w-12 text-red-500 mx-auto" />
            <h3 className="font-semibold text-lg text-red-600">تعذر بدء عملية الدفع</h3>
            <p className="text-sm text-muted-foreground">{errorMsg}</p>
            <Button variant="outline" className="w-full" onClick={() => setStatus("IDLE")}>
              إعادة المحاولة
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
