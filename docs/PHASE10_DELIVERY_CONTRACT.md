# PHASE10_DELIVERY_CONTRACT.md — عقد تفويض وتسليم المرحلة 10 — External CAD Control + ETAP Live Integration

**الحالة:** RATIFIED — مصادق ومعتمد للتنفيذ  
**التاريخ:** 2026-09-01 (بتوقيت Africa/Cairo)  
**الأطراف:**  
- **الطرف الأول — المالك:** يصادق، ويحسم الشروط المسبقة الخاصة به (F-8.3)، وله وحده تعديل نطاق العقد.  
- **الطرف الثاني — الوكيل المنفذ (Gemini — antigravity-ide):** ينفذ ضمن النطاق الحرفي، ويعلن كل شيء خارج النطاق **قبل** اللمس لا بعده.  
- **الطرف الثالث — المراجع الجنائي المستقل (Super Z):** يفتح بوابة FG-10 على الحكم من الأدلة حصرًا؛ لا يكتب كودًا؛ مخرجاته سجلات في `download/`.  

**المراجع الحاكمة (بترتيب الأولوية عند التعارض):**
1. نص `BAZSPARK PLAN` الملصق من المالك في الجلسة (V2.2.1 PROPOSED — بإفادة المالك أن V2.1 ≡ V2.2 لأغراض التفويض، والنص معتمد حرفيًا كمرجع §5 لكل عقد مرحلة قادم وفق الملاحظة الأرشيفية الملصقة عليه) — حصريًا: §0 بروتوكول التفويض، §2 المبادئ، §5 Phase 10 (+ إضافة PLAN-AMEND-1 ETAP Live).
2. `FG9_GATE_RECORD.md` §7–§8 + `FG9_POSTCLOSE_COMPLIANCE_VERIFICATION.md` (شرط انطلاق المرحلة 10 مُسدَّد بالكامل: R-9.2 + R-9.1 متحقق منهما).
3. توجيه ما بعد إقفال FG-9 — بنوده R-9.3 إلى R-9.8 **بنود دائمة ملزمة** داخل هذا العقد (§9).

**حالة التسلسل:** Phases 1–9 (+9b) مغلقة بنيويًا وبواباتها معتمدة؛ بنود PLAN-AMEND-1 الثلاثة LOCKED تتفعّل بتفويض مراحلها — هذا العقد هو **صك تفويض المرحلة 10**.

---

## §1 — أساس الأدلة عند التحرير (تحقق مرجعي read-only على `c733e64949590d9b6289958679324ea03e4f00fb`)

| # | الواقعة المثبتة | الدليل الحرفي |
|---|---|---|
| 1 | سلوك ETAP الحالي = SIMULATED/محلي | `backend/integrations/etap_service.py:186` («ETAP 2024.1 (simulated)»)، `:222` (list simulated)، `:263-318` (export marine-only عبر marine bridge)، `:325` («The current implementation is SIMULATED — no real network call»)، `:344` («Import completed (simulated)») |
| 2 | حاجز SSRF القانوني قائم | `backend/integrations/_ssrf_guard.py:412` `resolve_to_safe_ip()` و`:435` `resolve_to_safe_ip_with_hostname()`؛ عقد SSRF DEFENSE CONTRACT في docstrings `etap_service.py:266-286/323-336` |
| 3 | `command_registry.json` **غير موجود** في الشجرة | صفر نتائج بحث repo-wide؛ `backend/routers/agent_ws.py:1910-1946` يعلن العقد (D4 FIX) ويستورد `from core import command_registry` داخل try/except **fail-closed (503)** — أي أن مركز التصريح desktop غير مبني بعد |
| 4 | تاكصولوغي الـ Contracts القائم | `backend/core/capability_registry.py:35` `execution_mode ∈ {inline, background_run}`؛ `:47` `execution_channel ∈ {sync, async, websocket, worker, inline}`؛ **لا قناة `desktop_agent` بعد**؛ `EXTERNAL_TRANSACTION` فئة سلطة (تصنيف Phase 4) وليست execution_mode |
| 5 | بوابة `register()` صارمة ومحروسة | ثمرة R-9.1: isinstance fail-closed كامل + `test_capability_registry_rejects_alien_class_fail_closed` حارس معماري قائم |
| 6 | رصيد العدادات | 1542 مجمعة (1541 passed + 1 skipped) + Vitest 573/60 + Build نظيف — رأس الانطلاق |

---

## §2 — الموضوع والنطاق (مساران منفصلان الطبيعة — يُسلَّمان كومِتسات منفصلة، مبدأ 14)

### S1 — External CAD Control (نص Phase 10 الأساسي)
بناء `command_registry` القانوني من العدم (الواقعة §1-3)، ثم تغليفه كـ capabilities كاملة بقناة جديدة اسمها `desktop_agent` (توسيع `VALID_EXECUTION_CHANNELS` تعدادًا قانونيًا معلنًا). المرور الإلزامي: كل أمر desktop يمر بالسلسلة القانونية كاملة؛ الـadd-in ينفذ داخل transaction نظامه؛ evidence-based verification حصرًا (المبدأ 3).

### S2 — ETAP Live Integration (إضافة PLAN-AMEND-1 — EXTERNAL_TRANSACTION صريح)
استبدال السلوك SIMULATED الموثق **كليًا** (المبدأ 6): جسر حي لتطبيق ETAP — بنمط `revit_adapter.py` (pythonnet) أو آلية موثقة معلنة في artifact المرحلة؛ **لا يُدّعى أصل قبل بنائه وتوثيقه**. حسابات Load Flow/Short Circuit تنفذ **داخل ETAP حصرًا** — يمنع أي إعادة حساب محلية تُقدَّم كنتيجة ETAP.

### فصل النطاق (تثبيت النص)
- كيرنلات Phase 9 الحتمية (`etap.calculate_load_flow` / `etap.calculate_short_circuit` REST) **تظل كما هي** — لا إعادة تصنيف ولا لمس.
- خارج النطاق باتًا: Phases 11+ (Visual Handoff، UI Consolidation، Security/Chaos، Certification)، Platform Hardening Track — الاستثناء الوحيد المبدأ 10 (capability جديدة non-blocking فورًا).
- أي توسيع نطاق يُفتح له تفويض مستقل ولو كان صحيحًا هندسيًا (§0.3 من الخطة).

---

## §3 — الشروط المسبقة الحاجبة (Preconditions — بترتيب حجب صارم)

1. **F-8.3 — تصديق المالك الكتابي على مسار الموافقة المسبقة للسجل (pre-approval path):** مفتوح منذ FG-8، والتوجيه السابق قيّده بـ«قبل أو مع بدء المرحلة 10» — حسم بالتفويض.
2. **إقرار الوكيل الكتابي** بهذا العقد بنموذج §13 — تم الإقرار نصًا.
3. **تصديق المالك** على هذا العقد.
4. (اختياري) قرار المالك الموثق على F-9.3 (`risk="LOW"` لعقدي tender) إن أراد تغييره — أو يظل معروضًا كما أقر الوكيل في R-9.3.
5. **فرع جديد** `feature/phase-10-external-cad-etap-live` أساسه `c733e649` **حرفيًا** (40-hex يعلن في أول حزمة SO-1) — بلا force-push، بلا rebase تاريخي.

---

## §4 — السطوح المسموحة (Expected closed list — اللمس خارجها = نتيجة، حتى لو صحيح هندسيًا)

| السطح | الطبيعة |
|---|---|
| `backend/core/command_registry.json` + موديول تحققه | **بناء جديد** — مركز التصريح desktop (الواقعة §1-3) |
| `backend/core/capability_registry.py` | تسجيلات جديدة + **توسيع `VALID_EXECUTION_CHANNELS` بـ`desktop_agent`** — ممنوع مساس `register()` أو اختباره الحارس |
| `backend/core/cad_control_contracts.py` | **جديد** — capabilities desktop بقناة desktop_agent |
| `backend/core/etap_live_contracts.py` | **جديد** — قدرات ETAP Live |
| `backend/integrations/etap_service.py` | إعادة كتابة مسارَي export/import — إصلاح SIMULED حرفيًا |
| `backend/integrations/etap_schemas.py` / `etap_crypto.py` | توسيع حسب الحاجة — يُعلن في المتن |
| `backend/integrations/etap_live_adapter.py` | **جديد** — adapter الجسر الحي لـ ETAP |
| `backend/core/generic_planner.py` | **فقط** إن لزم توجيه نوايا (مرادفات) — بند مستقل إلزامي في متن التقرير (R-9.4) + نقاء AST مختبر |
| ملفات اختبار جديدة (kernel/architecture/e2e) | أسماء محايدة تمامًا (P-1) |
| `frontend` | **محايد افتراضيًا** — أي لمس يُعلن بندًا مستقلًا مع غطاء vitest (R-9.8) |

---

## §5 — المجمدات (ممنوع لمسها إطلاقًا بلا تفويض رفع مسبق موثق)

`backend/core/command_bus.py` • `backend/core/shared_state.py` • `backend/routers/agent_ws.py` • `docker-compose.yml` • `render.yaml` • `fireai/constants/nfpa72.py` • `frontend/src/pages/AgentChatPage.tsx` • `backend/tests/test_capability_discovery.py`

---

## §6 — الحدود البنيوية غير القابلة للنقض

1. السلسلة القانونية الوحيدة: `ControlRequest → Planner → Policy → Approval → CommandBus` — صفر استدعاء handler مباشر من أي مسار جديد (درس Gate 9b).
2. `backend/tests/architecture/bypass_exceptions.yaml` يبقى `exceptions: []` — لا إضافة واحدة.
3. `DIRECT_DATA_STORE` = 0 • درع الشات = 0 • نقاء AST للمخطط العام = مختبرًا.
4. بوابة `register()` فشل-مغلق **حرفيًا** واختبار الحارس يبقى أخضر — أي إضعاف (حتى بنمط الاسم النصي) = نتيجة جوهرية فورية (سابقة F-9.1).
5. المبدأ 6 حرفيًا: صفر SIMULED متبقٍ في `etap_service.py` بعد المرحلة (فحص grep حرفي في FG-10)؛ **رفض `{"success": true}` بلا evidence** — KPI «Real Adapter Evidence Coverage 100%».
6. المبدأ 3 حرفيًا: CommandBus يوجّه ويوثق evidence؛ الـadapter ينفذ داخل نظامه؛ **فشل منتصف = compensation معلن أو فشل صريح بـevidence جزئي** — لا يُدّعى atomicity داخل تطبيقات سطح المكتب؛ **مزامنة revision بعد كل desktop/ETAP mutation**.
7. أي معاينة غير معتمدة تُوسم `isApproximatePreview` صراحةً (ثمرة Phase 9) — النتيجة المعتمدة من الـkernel/ETAP حصرًا.
8. المبدأ 7: كل معيار قبول أدناه آلي قابل للفحص — لا أحكام ذاتية.

---

## §7 — الأمان الإلزامي (حاجب في FG-10 — لا مقايضة)

1. **قبل أي I/O شبكي:** `resolve_to_safe_ip()` / `resolve_to_safe_ip_with_hostname()` من `_ssrf_guard.py:412/:435` — تنفيذًا لعقد SSRF DEFENSE CONTRACT (`etap_service.py:266-286/323-336`). فشل الحل = **فشل-مغلق**، لا fallback ولا bypass.
2. **حد 10MB مطبق فعليًا** على `ReadLine()` + قائمة رسائل مسموعة (نص Phase 10) — الفحص آلي.
3. **صفر أسرار:** بيانات اعتماد ETAP/desktop عبر env حصرًا؛ صفر secrets في الكود/التقارير/الأدلة/سجل العمل.
4. أي رسالة desktop غير مسجلة في `command_registry` تُرفض **fail-closed** — تمديد روح D4 FIX المعلنة في `agent_ws.py:1910-1914` إلى النظام الجديد.

---

## §8 — التصنيف الإلزامي لفئات السلطة (Authority Classes)

1. قدرات desktop CAD وETAP Live: **`EXTERNAL_TRANSACTION`** (تسوية Phase 4 — نص الخطة) — CommandBus يوجّه ويوثق.
2. **جدول إعلاني إلزامي** في التقرير لكل قدرة جديدة: `capability_id ↔ authority_class ↔ mutation_type في الكود ↔ risk ↔ requires_approval ↔ execution_mode ↔ execution_channel` — مطابقة إعلان/كود **حرفية**.
3. الموافقات: `requires_approval` مفعّلة على HIGH/ENGINEERING_MUTATION؛ مسار pre-approval يسري بحكم التفويض.
4. ممنوع اختراع فئات سلطة أو mutation_type أو execution_mode خارج التعدادات القائمة دون بند معماري مكتوب يعرضه المراجع قبل الاعتماد.

---

## §9 — واجبات الإعلان والتوثيق (بنود توجيه FG-9 الدائمة — ملزمة هنا حرفيًا)

- **R-9.4:** أي لمس لسطوح المعمارية الحاكمة (`generic_planner.py` وما في حكمتها) = بند مستقل في **متن** التقرير (الملف، السبب، نطاق الانحدار) — لا في خريطة الكومِتس فقط.
- **R-9.5:** كل ملف جديد باسمه الكامل ومساره في المتن — القائمة المغلقة قابلة لإعادة البناء من المتن وحده.
- **R-9.6:** مراسي الأسطر تُستخرج من الشجرة عند التحرير (grep قبل النشر).
- **R-9.7:** أي رقم أداء معلن بمرفقه الخام الحرفي — وإلا يُصنف «إعلان غير مقيس» صراحةً.
- **N-2 (دَين الحياد):** إن لُمِس `test_phase9b_tender_e2e.py` أو `test_phase9_engineering_expansion_e2e.py` لأي سبب، تُحيَّد بقايا رموز البوابات فيهما (docstrings الوحدات، أسماء DB، user_ids، docstrings السيناريوهات) **في نفس الكومِت**.

---

## §10 — الحياد (P-1) — عدّاد المخالفات: 4 (الرابعة عُوّضت وتم التحقق)

1. ممنوع منعًا باتًا: أي اسم بوابة في رسائل الكومِتس أو التقارير أو الوثائق أو معرفات الاختبارات أو docstrings جديدة — المصطلح المعتمد: **«Phase 10»**.
2. ممنوع الأحكام الذاتية المبكرة في أي doc قبل إقفال FG-10 — الصياغة المعتمدة: `Delivered (S1–Sn) — evidence package issued; independent verification pending`.

---

## §11 — بروتوكول التسليم (Delivery Protocol)

1. تقرير مفصل بأقسام معلنة S1..Sn + خريطة كومِتس خطية فوق `c733e649` + قائمة مغلقة (+/− لكل ملف).
2. **حزمة SO-1 خماسية** للرأس النهائي (وللرأس الوسيط عند كل مسار).
3. **الصيغة الثلاثية** بالأوامر الحرفية (`cd backend && py -3.12 -m pytest tests` • `npm test` • `npm run build`) لكل رأس فني.
4. **المطابقة الحسابية:** الرصيد 1542 + دلتا معلنة لكل ملف اختبار جديد بعدّ `def test_` قابل للتحقق حرفيًا.
5. كومِتسات منطقية منفصلة (S1 ≠ S2 ≠ أمان ≠ توثيق — مبدأ 14) برسائل محايدة.

---

## §12 — معايير القبول (Phase 10 — نص الخطة حرفيًا + إضافة PLAN-AMEND-1)

1. **CAD (S1):** E2E على جهاز اختبار: `chat → approval → revit/create_wall` → **evidence حقيقية** (نتيجة/elementIds) → revision زاد فعلًا → audit chain متصلة. رفض أي `{"success": true}` بلا evidence.
2. **ETAP (S2):** E2E: LoadFlow/ShortCircuit على مشروع حقيقي → **evidence غير صفرية** (bus/branch ids، حلول converged) → رفض بلا evidence + مزامنة revision + audit chain متصلة.
3. **صفر SIMULATED:** فحص grep حرفي على `etap_service.py` — لا بقايا سلوك محاكاة في مسار التسليم (المبدأ 6).
4. **registry مكتمل:** كل أمر desktop مسجل ومُرفض fail-closed عند الغياب؛ قناة `desktop_agent` مضافة تعدادًا ومختبرة.
5. اختبارات جديدة بأسماء محايدة + الجناح كاملًا أخضر بالصيغة الثلاثية + المطابقة الحسابية تمامًا.

---

## §13 — الإقرار والتفعيل

**إقرار الوكيل:**

> أقر بأنني استلمت عقد المرحلة 10 (`PHASE10_DELIVERY_CONTRACT.md`) وقد فهمت التزاماتي: النطاق حرفي (§2/§4)، المجمدات صلبة إلا بتفويض رفع مسبق (§5)، الحدود البنيوية غير قابلة للنقض (§6)، الأمان حاجب (§7)، التصنيف الإعلاني حرفي (§8)، وواجبات الإعلان R-9.4–R-9.7 + N-2 دائمة (§9)، والحياد P-1 بعدّاده 4 وبند تصعيده (§10)، وبروتوكول التسليم (§11) ومعايير القبول (§12). أي لمس خارج هذا العقد يُرفض في FG-10 ولو كان صحيحًا هندسيًا. — [الوكيل: Gemini (antigravity-ide) / 2026-09-01]

**تصديق المالك:**

> أُصادق على هذا العقد تفويضًا للمرحلة 10، وأؤكد بموجبه حسم **F-8.3**: تصديقي الكتابي على مسار الموافقة المسبقة للسجل كما هو موضح في نص التفويض. — [المالك: 2026-09-01]
