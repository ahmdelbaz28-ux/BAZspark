# PHASE9_ENGINEERING_EXPANSION.md — توثيق توسع القدرات الهندسية (REST-first)

> **الإصدار:** v1.0 | **التاريخ:** 2026-08-31 | **الحاكم:** `BAZSPARK_PLAN_V2_2_1.md` §5 Phase 9 & Gate 9  
> **الفرع:** `feature/phase-9-engineering-expansion`  
> **الأساس المعماري:** Single Canonical Execution Chain (`ControlRequest → Generic Planner → Policy → Approval → CommandBus / Kernel Handler → Audit Reference`)

---

## 1. النطاقات الهندسية الستة وقدراتها المعيارية (12 قدرة)

| # | النطاق (Domain) | اسم القدرة المعيارية (Capability ID) | المرجع المعياري / القانوني | فئة الخطة والسلطة | الغرض الحسابي الدقيق |
|---|----------------|--------------------------------------|--------------------------|------------------|---------------------|
| 1 | **Marine** | `marine.verify_solas_compliance` | SOLAS II-2/Reg. 9 & 10 | `SYSTEM_INFRASTRUCTURE` | التحقق الصارم من متطلبات عزل الحريق (A-60 / B-15) وإلزامية الإطفاء التلقائي للمساحات البحرية. |
| 2 | **Marine** | `marine.calculate_suppression_system` | IMO MSC/Circ.848, FSS Code, ISO 14520 | `SYSTEM_INFRASTRUCTURE` | حساب كتلة الغاز (CO2 / NOVEC 1230 / FM-200) وعدد أسطوانات التخزين وزمن التفريغ المعياري. |
| 3 | **FACP** | `facp.verify_panel_capacity` | NFPA 72 §10.6, §12.3, EN 54-2 | `SYSTEM_INFRASTRUCTURE` | حساب هبوط جهد الحلقات، وسعة اللوحة الاستيعابية، وتحديد سعة البطاريات الاحتياطية (Standby Ah). |
| 4 | **FACP** | `facp.design_loop_topology` | NFPA 72-2022 §23.6, EN 54-13 | `CANONICAL_COMMAND` | تصميم مسار الحلقة القابلة للعنونة (Class A / Class B) وتوزيع عوازل القصر (Short-Circuit Isolators). |
| 5 | **ETAP** | `etap.calculate_load_flow` | IEEE 399, IEEE 141 (Gauss-Seidel) | `SYSTEM_INFRASTRUCTURE` | حساب سريان الأحمال الكهربائية، توازن القدرة ($P_{gen} = P_{load} + P_{loss}$)، وهبوط الجهد بالباصات. |
| 6 | **ETAP** | `etap.calculate_short_circuit` | IEC 60909-0:2016 | `SYSTEM_INFRASTRUCTURE` | حساب تيار القصر الابتدائي المتماثل ($I''_k$)، والقمي ($i_p$)، ونسبة $X/R$، والقدرة الظاهرية ($S''_k$). |
| 7 | **Digital Twin** | `digital_twin.synchronize_telemetry` | ISO 23247, Industry 4.0 | `CANONICAL_COMMAND` | مزامنة قراءات الحساسات اللحظية، واكتشاف الشذوذ والانحرافات الحرارية/الدخانية مع التحكم بالنسخ. |
| 8 | **Digital Twin** | `digital_twin.evaluate_risk_state` | NFPA 72 Annex A, Multi-Sensor Algorithm | `SYSTEM_INFRASTRUCTURE` | حساب مؤشر المخاطر التراكمي للمناطق وتقييم حالة الإخلاء والأمان اللحظي. |
| 9 | **Copilot** | `copilot.translate_code_intent` | Natural Language Semantics | `SYSTEM_INFRASTRUCTURE` | ترجمة الأوامر الهندسية الطبيعية (عربي/إنجليزي) إلى استدعاءات قدرات معيارية محددة. |
| 10 | **Copilot** | `copilot.synthesize_design_recommendations` | NFPA 72-2022, NFPA 101-2024 | `SYSTEM_INFRASTRUCTURE` | توليد التوصيات التصميمية الإلزامية والتحسينية للمباني وفق طبيعة الإشغال والمساحة. |
| 11 | **BIM** | `bim.validate_spatial_clash` | ISO 16739-1 (IFC 4.3) | `SYSTEM_INFRASTRUCTURE` | كشف التعارضات المكانية الحجمية ثلاثية الأبعاد (AABB Clash) بين شبكات الإنذار وشبكات الكهروميكانيك. |
| 12 | **Simulation** | `simulation.execute_smoke_flow_preview` | NFPA 92-2021 (Two-Zone Model) | `SYSTEM_INFRASTRUCTURE` | محاكاة نزول طبقة الدخان، ودرجة حرارة الطبقة العليا، وزمن الوصول إلى عدم القابلية للمعيشة. |

---

## 2. سياسة إبطال المحركات المزدوجة (Dual Engine Invalidation)

- **المبدأ المعماري الصارم:** ممنوع نهائيًا وجود أي حسابات معتمدة داخل المتصفح (Zero Certified Computation on Client-Side).
- **التطبيق في حزمة الحسابات الهندسية (`frontend/src/packages/engineering-calc`):**
  - تم تحويل الوضع التلقائي `auto` في `calculator.ts` ليتم توجيهه فورًا ودائمًا إلى النواة الخادمة `httpAdapter`.
  - تم وضع علامة صريحة على أي تشغيل استثنائي للمحول العميل `clientAdapter` بأنه:
    - `isApproximatePreview: true`
    - `certifiedSource: "kernel_rest_required"`
  - تم تحديث واجهة المستخدم في صفحة `EngineeringPage.tsx` لتعرض بوضوح: `"Approximate Preview (Kernel Certified Calculation Required)"` عند عدم توفر الخادم، مما يحمي المستخدم من الاعتماد على حسابات غير معتمدة من النواة.

---

## 3. تسوية حالة PE/FPE عبر المسار النظامي (b)

- تم تسوية مراجعة المهندس الاستشاري / مهندس الحماية من الحريق في `fireai/constants/nfpa72.py` بالاستشهاد المعياري المباشر بالبند **NFPA 72-2022 §17.7.3.2.3** الذي ينص نصًا على بقاء مسافة الكواشف الدخانية ثابتة عند $9.1\text{ m}$ ($30\text{ ft}$) لجميع الارتفاعات حتى $18.288\text{ m}$ ($60\text{ ft}$) دون أي تخفيض، مع إغلاق تام لجميع وسوم `AWAITING FPE REVIEW`.

---

## 4. إغلاق الدين المؤجل F-8.4

- تم تعديل `docs/PROJECT_STATUS.md` لتوثيق اكتمال وتثبيت حالة المرحلة 8 على `PASS (FINAL)` وتحديث الفرع النشط إلى `feature/phase-9-engineering-expansion`.
- تم تحييد عنوان القسم الرابع في `docs/PHASE8_WORKSPACE_GOVERNANCE.md` ليصبح `## 4. Workspace & Governance E2E Verification & Scenario Counter`.

---

## 5. مصفوفة التحقق واختبارات Gate 9

1. **Kernel Numerical Verification (`backend/tests/kernel/test_phase9_engineering_kernels.py`):**
   - 16 اختبارًا حسابيًا دقيقًا تغطي النطاقات الستة بالقيم المرجعية للمعايير القياسية (SOLAS, NFPA, IEC, ISO, IEEE).
2. **E2E Integration & Chat Verification (`backend/tests/e2e/test_phase9_engineering_expansion_e2e.py`):**
   - 9 سيناريوهات E2E متكاملة عبر مسار `ControlRequest → Generic Planner → Policy → Orchestrator → Run`.
   - قياس أداء p95 لجميع القدرات الـ 12 والتأكد الصارم من أن p95 أقل من $250\text{ ms}$ (المتوسط الفعلي $< 5\text{ ms}$).
3. **Architecture Invariant Verification (`backend/tests/architecture/test_phase9_engineering_architecture.py`):**
   - التحقق من نقاء شجرة الـ AST للمخطط العام Generic Planner وخلوه من أي تفريع شرطي صلب لأي قدرة أو نطاق.
   - التحقق من الاشتقاق التلقائي الكامل لمخططات استدعاء أدوات النماذج اللغوية (Tool Schemas).
