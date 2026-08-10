# Akamai EdgeWorkers — verify-origin

`verify-origin` EdgeWorker يحقن `X-Akamai-Origin-Token` قبل تمرير الطلب للـ origin،
ويتحقق منه `backend/akamai_middleware.py`. هذا يمنع تجاوز WAF/Bot Manager
بإرسال طلبات مباشرة لعنوان الـ origin (HF Space / Vercel).

## P0-15 FIX (2026-08-09) — لا توكن مدمج في الكود

المصدر القديم كان قيمة placeholder مكتوبة في السورس (`REPLACE_WITH_SECRET_FROM_PROPERTY_MANAGER`).
أي نشر يستخدم هذا الملف دون الاستبدال كان سيحقن توكن خاطئ — والتحقق في الـ backend
يستمر بالمرور الخطأ، أو يفسد المصادقة بصمت.

**السلوك الجديد (fail-closed):**

- يُقرأ التوكن من متغير Property Manager: `PMUSER_origin_token`.
- إذا لم يُضبط المتغير → يرد الـ EdgeWorker بـ **403** مع الرسالة
  `Origin token not configured` — لا يمرر طلباً واحداً دون توكن صحيح.

## خطوات النشر (إلزامية)

1. **ضبط المتغير في Property Manager:**
   - Property Manager → Edit New Version → **Variables** → Add Variable.
   - الاسم: `PMUSER_origin_token`
   - القيمة: سلسلة عشوائية طويلة (تطابق قيمة `AKAMAI_REQUIRE_ORIGIN_TOKEN`
     في بيئة الـ backend).
   - مثال للتوليد محلياً:
     ```bash
     python -c "import secrets; print(secrets.token_urlsafe(48))"
     ```
   - **لا تضع القيمة في git أبداً** — المتغير يُحفظ فقط في Akamai.
2. شغّل الـ EdgeWorker المحدّث (بعد التعديلات في `main.js`) عبر
   EdgeWorkers API أو Control Center كالمعتاد.
3. تأكد أن البيئة في Property يمكنها الوصول للمتغير (Deploy access):
   EdgeWorkers → Manage Tokens/Access → اربط التوكين بالسياسة المستخدمة.
4. بعد النشر، اختبر أن:
   - طلب مباشرة إلى أصل خارج Akamai (بدون مسار الـ Edge) يُرفض من الـ backend.
   - طلب عابر للـ Akamai يمر مع `X-Akamai-Origin-Token`.

## Back compatibility

- السلوك متماثل عدا نقطة: إذا نُشِّرت النسخة الجديدة دون ضبط المتغير —
  كل الطلبات لن تحصل 403 من الـ Edge، وهذا مقصود (fail-closed).
  أي اعتماد على عبور verifier بدون توكن يُعتبر ثغرة Launch blocker.