# PHASE11_OPS_RUNBOOK.md — دليل التشغيل والجاهزية الإنتاجية للتكامل مع ETAP Live

**الإصدار:** 1.0.0  
**الحالة:** APPROVED FOR PRODUCTION  
**المعيار الهندسي:** IEEE 399 (Brown Book) / IEC 60909-0:2016 / NFPA 70 & 72  
**النطاق:** تشغيل وحماية وصيانة جسر التكامل الحي بين BAZspark ومحرك ETAP Live  

---

## §1 — قائمة التحقق قبل النشر للإنتاج (Deployment Checklist)

| # | بند التحقق | الإجراء المطلوب | وسيلة التحقق المؤتمتة |
|---|---|---|---|
| 1 | **SSRF Defense Gate** | التأكد من أن عنوان الخادم المضيف لـ ETAP لا يقع ضمن النطاقات الخاصة أو الاسترجاعية (Loopback/Private/Metadata). | استدعاء `resolve_to_safe_ip(host)` الإلزامي قبل أي اتصال. |
| 2 | **10MB Buffer Ceiling** | التحقق من سقف 10MB على تدفق البيانات الصادرة والواردة `MAX_READLINE_BYTES`. | رفض فوري لأي حمولة تتجاوز 10MB بواسطة `EtapSecurityViolation`. |
| 3 | **License Seats Concurrency** | ضبط سعة المقاعد المتزامنة `max_concurrent_requests` وفق ترخيص ETAP Enterprise. | حارس `ConcurrencyLimiter` مع دلالات 429 Too Many Requests. |
| 4 | **Circuit Breaker Configuration** | ضبط عتبة الفشل (3 محاولات) وفترة الاستشفاء (10 ثوانٍ) واستراتيجية Fail-Closed. | مراقبة عداد `circuit_opens_count` في `default_etap_telemetry`. |
| 5 | **Cryptographic Checksums** | التأكد من سلامة الحالات الذهبية المسجلة تحت `tests/golden/etap/`. | اجتياز اختبار `test_golden_fixtures_sha256_checksum_integrity`. |
| 6 | **Zero Secrets in Code/Config** | التحقق من تشفير وتمرير جميع بيانات الاعتماد عبر متغيرات البيئة المشفرة. | الفحص الأمني عبر `secret-scan` و `bandit`. |

---

## §2 — إجراءات تدوير الأسرار وبيانات الاعتماد (Secret Rotation)

### 1) تدوير كلمة مرور خدمة ETAP
1. إنشاء كلمة مرور عشوائية مشفرة:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. تحديث الإعدادات في قاعدة البيانات عبر واجهة الخدمة المشفرة `EtapService.update_settings(...)` التي تطبق تشفير AES-GCM تلقائياً.
3. التحقق من الاتصال الحي عبر:
   ```bash
   python scripts/etap_golden_revalidate.py --verify-only
   ```

### 2) تدوير شهادات TLS/SSL
1. وضع الشهادات الجديدة في مسار الشهادات المعتمد للنظام.
2. التأكد من تطابق اسم المضيف المعتمد (SAN) مع السجل المصرح به في DNS الآمن.
3. اختبار المصافحة باستخدام الفحص الآمن لمنع أي هجوم Man-in-the-Middle.

---

## §3 — كتيبات معالجة الحوادث (Incident Response Playbooks)

### 📌 Playbook 1: انطلاق إنذار حظر SSRF (`ssrf_blocked_count > 0`)
* **العَرَض:** تسجيل حدث `etap.resolve` بحالة فشل وارتفاع عداد `ssrf_blocked_count`.
* **السبب الجذري المحتمل:** محاولة توجيه طلبات إلى نطاق داخلي، أو عنوان IP استرجاعي (127.0.0.1)، أو عنوان بيانات سحابية (169.254.169.254)، أو هجوم DNS Rebinding.
* **الإجراء الفوري:**
  1. التحقق من عنوان المضيف في سجلات التدقيق:
     ```python
     from backend.core.etap_telemetry import default_etap_telemetry
     events = default_etap_telemetry.get_events(limit=10, event_type="etap.resolve")
     ```
  2. عزل مصدر الطلب وتأكيد رفضه التلقائي من طبقة الحماية (Fail-Closed).
  3. حظر النطاق أو اسم المستخدم في سجل الحوكمة المؤسسية.

---

### 📌 Playbook 2: فتح قاطع الدائرة (`CircuitBreaker State = OPEN`)
* **العَرَض:** رفض فوري للطلبات باستثناء `CircuitBreakerOpenError` وارتفاع عداد `circuit_opens_count`.
* **السبب الجذري المحتمل:** خادم ETAP الخارجي غير متاح، أو انقطاع في الشبكة، أو تجاوز مهلة الاستجابة لـ 3 محاولات متتالية.
* **الإجراء الفوري:**
  1. مراجعة حالة خادم ETAP المضيف والتأكد من تشغيل منفذ الخدمة (Port 18888).
  2. عدم محاولة تجاوز القاطع أو تحويل النظام إلى وضع المحاكاة الصامت (Silent Mock Fallback محظور قطيعاً).
  3. انتظار انتهاء فترة الاستشفاء (10 ثوانٍ) ليدخل القاطع تلقائياً في طور `HALF_OPEN`.
  4. في حال استعادة الخدمة، يتيح القاطع فحصاً تجريبياً، وبنجاح فحصين متتاليين يعود تلقائياً إلى طور `CLOSED`.
  5. لإعادة الضبط اليدوي في الحالات الطارئة:
     ```python
     from backend.integrations.etap_live_adapter import reset_all_circuit_breakers
     reset_all_circuit_breakers()
     ```

---

### 📌 Playbook 3: استنفاد ميزانية المهلة الزمنية الكلية (`TimeoutBudgetExceededError`)
* **العَرَض:** إخفاق الحسابات الهندسية برمي `TimeoutBudgetExceededError`.
* **السبب الجذري المحتمل:** شبكة بطيئة أو دراسة شبكة معقدة تتجاوز ميزانية الـ 30 ثانية.
* **الإجراء الفوري:**
  1. فحص زمن الاستجابة P95 عبر `default_etap_telemetry.get_slo_metrics()`.
  2. التأكد من تقليل عدد تكرارات نيوتن-رافسون إلى الحدود المثلى (50 تكراراً).
  3. ضبط ميزانية المهلة في `RetryPolicy(total_timeout_budget_seconds=45.0)` إن لزم للدراسات الكبرى.

---

## §4 — إجراءات التراجع الآمن والتعافي (Rollback & Recovery)

1. في حال حدوث خلل إنتاجي يستدعي التراجع الفوري:
   - التراجع إلى الإصدار المعتمد السابق `P10-FROZEN` (`49549ba89237bf1bdf8e76d7e1450f0a5c6533a8`).
2. تأكيد مبدأ Fail-Closed:
   - يمنع منعاً باتاً تحت أي ظرف تشغيلي إرجاع نتائج محاكاة وهمية أو بيانات فارغة ناجحة كاذبة.
   - الرفض الصريح هو السلوك المعتمد لضمان السلامة الهندسية للمنشآت الحيوية والكهربائية.
