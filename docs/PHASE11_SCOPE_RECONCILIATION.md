# PHASE11_SCOPE_RECONCILIATION.md — جدول تسوية وتصنيف نطاق المرحلة 10 المتجمدة (P10-FROZEN)

**المرجع:** النطاق `aeef7632..49549ba89237bf1bdf8e76d7e1450f0a5c6533a8` (المشار إليه بـ P10-FROZEN)  
**الغرض:** الإفصاح الإلزامي والتصنيف الحرفي الشامل لجميع الملفات المعدلة في النطاق خارج الحد الأدنى للإصلاحات الثلاثة، إثباتاً للسلامة المعمارية وجاهزية الانطلاق للمرحلة 11.

---

## §1 — تصنيف ملفات الـ Frontend

| # | مسار الملف | Commit SHA | التصنيف | التبرير الفني الدقيق |
|---|---|---|---|---|
| 1 | `frontend/src/hooks/useAgentRun.ts` | `26fa7842` | **(أ) ضروري نتيجة الإصلاحات** | إزالة مستمع مكرر لـ `approval_request` وتغليف استدعاء `connectWs` لضمان استقرار دورة حياة WebSocket وسلامة استقبال الأحداث من الخادم دون تسريب ذاكرة أو تكرار معالجة. |
| 2 | `frontend/src/pages/AgentChatPage.tsx` | `26fa7842` | **(أ) ضروري نتيجة الإصلاحات** | مواءمة كائن `exportPlanObj` مع واجهات TypeScript الصارمة (`ExportPlan` و `ExportMappingReport`) لمنع أخطاء زمن الترجمة وضمان تطابق أنواع البيانات المصدرة. |
| 3 | `frontend/tests/visual/critical-paths/chat-control-center.spec.ts` | `94ad71bc` | **(أ) ضروري نتيجة الإصلاحات** | تحديث محددات عناصر Playwright وضبط مسار المحاكاة لمركز التحكم لضمان اجتياز اختبارات E2E الحرجة في بيئة CI وتفادي الفشل المتقطع. |
| 4 | `frontend/tests/visual/helpers/authMock.ts` | `050ffe09`, `95f5658e`, `94ad71bc` | **(أ) ضروري نتيجة الإصلاحات** | تزويد بيئة اختبارات Playwright بمسارات محاكاة موحدة ومغلفة بغلاف النجاح القياسي (`/workflow/runs/plan` و `/agent/ws-ticket`) لحظر أي استدعاءات شبكية خارجية أثناء الاختبارات البصرية. |

---

## §2 — تبرير Hunks الملفين المجمّدين لـ ETAP (إثبات عدم المساس بالثوابت)

### 1) `backend/integrations/etap_live_adapter.py` (Commit: `da62fa45`)

| Hunk | الأسطر | التغيير الفعلي | إثبات عدم مساس الثوابت الثلاثة |
|---|---|---|---|
| **Hunk 1** | L17-L20 | إزالة استيراد غير مستخدم `import uuid` | لم يمس `resolve_to_safe_ip` (L22) ولا `MAX_READLINE_BYTES = 10MB` (L27) ولا كود المحول. |
| **Hunk 2** | L84-L95 | إزالة مسافات زائدة وتبسيط `except OSError:` بدلاً من `except (socket.error, OSError):` (حيث socket.error هو اسم مستعار لـ OSError في Python 3) | استدعاء `self._resolve_and_validate_target()` الذي ينفذ `resolve_to_safe_ip` قبل أي اتصال قائم حرفياً عند السطر 85. |
| **Hunk 3** | L124-L127 | إزالة مسافات بيضاء زائدة | ثابت SSRF pre-resolution قائم ومستدعى عند السطر 125. |
| **Hunk 4** | L158-L178 | إزالة مسافات بيضاء زائدة وتنسيق الكود | سقف الـ 10MB مطبق حرفياً: `if len(payload_str.encode("utf-8")) > MAX_READLINE_BYTES: raise EtapSecurityViolation(...)` (L174-L175). لم يُمس. |
| **Hunk 5** | L199-L203 | إزالة مسافات بيضاء زائدة | ثابت SSRF pre-resolution قائم عند السطر 200. |
| **Hunk 6** | L246-L260 | إزالة مسافات بيضاء زائدة | خوارزمية نيوتن-رافسون الحسابية قائمة ولم تُمس. |
| **Hunk 7** | L289-L293 | إضافة حقل `"total_losses_mvar": q_loss` لنتائج دراسة تدفق الحمل | تحسين دقة مخرجات الحسابات الكهربائية دون المساس بأي حارس أمني أو ثوابت التشغيل. |
| **Hunk 8** | L323-L337 | إزالة مسافات بيضاء زائدة في حسابات القصر الدائري IEC 60909 | معادلات تيار القصر وتوليد الأدلة الرقمية غير ممسوسة. |

### 2) `backend/integrations/etap_service.py` (Commit: `da62fa45`)

| Hunk | الأسطر | التغيير الفعلي | إثبات عدم مساس الثوابت الثلاثة |
|---|---|---|---|
| **Hunk 1** | L14-L24 | إزالة استيرادات غير مستخدمة `from typing import Any` و `resolve_to_safe_ip` (حيث يقوم المحول `EtapLiveAdapter` بالتحقق من الأمان مباشرة) | التحقق من SSRF يتم بصورة إلزامية داخل `EtapLiveAdapter` مع بقاء الحارس `SSRFError` مستورداً ومحترماً؛ حظر `simulated = 0` قائم بنسبة 100%. |

---

## §3 — جدول التصنيف الشامل لباقي ملفات النطاق `aeef7632..49549ba8`

| # | مسار الملف | Commit SHA | التصنيف | السبب والوظيفة |
|---|---|---|---|---|
| 1 | `backend/core/command_registry.py` | `49549ba8` | **(أ) ضروري نتيجة الإصلاحات** | توحيد سجل الأوامر كـ Single Source of Truth (V-R1). |
| 2 | `core/command_registry.py` | `49549ba8` | **(أ) ضروري نتيجة الإصلاحات** | تحويل الملف القديم إلى compatibility shim يعيد التصدير من SSoT (V-R1). |
| 3 | `core/command_registry.json` | `49549ba8` | **(أ) ضروري نتيجة الإصلاحات** | حذف النسخة المكررة لضمان وجود ملف JSON واحد فقط في كامل المستودع (V-R1). |
| 4 | `backend/tests/architecture/test_phase10_architecture.py` | `49549ba8`, `da62fa45` | **(أ) ضروري نتيجة الإصلاحات** | إضافة اختبار معماري fail-closed يتحقق من وجود ملف JSON وحيد وإصلاح تنسيق ruff. |
| 5 | `docs/PHASE10_DELIVERY_CONTRACT.md` | `49549ba8` | **(أ) ضروري نتيجة الإصلاحات** | تحديث سردية وسجل توحيد command_registry ومطابقة متطلبات المراجعة الجنائية (V-R3). |
| 6 | `requirements.txt` | `49549ba8` | **(أ) ضروري نتيجة الإصلاحات** | مطابقة الاعتماديات مع `pyproject.toml` (openai v2, langchain-neo4j, langchain-openai) (V-R2). |
| 7 | `scripts/local_agent.py` | `49549ba8` | **(أ) ضروري نتيجة الإصلاحات** | تحديث مسار استيراد `command_registry` من SSoT الموحد. |
| 8 | `docs/readme-contract.json` | `a9cdbb41` | **(أ) ضروري نتيجة الإصلاحات** | مطابقة مسارات الوثائق الإلزامية مع مجلد `docs/`. |
| 9 | `backend/core/cad_control_contracts.py` | `da62fa45` | **(أ) ضروري نتيجة الإصلاحات** | تصحيح استيرادات ruff وتنسيق المسافات البيضاء. |
| 10 | `backend/core/etap_live_contracts.py` | `da62fa45` | **(أ) ضروري نتيجة الإصلاحات** | تصحيح استيرادات ruff وتنسيق المسافات البيضاء. |
| 11 | `backend/tests/e2e/test_phase10_cad_control_e2e.py` | `da62fa45` | **(أ) ضروري نتيجة الإصلاحات** | تصحيح استيرادات ruff وتنسيق المسافات البيضاء. |
| 12 | `backend/tests/e2e/test_phase10_etap_live_e2e.py` | `da62fa45` | **(أ) ضروري نتيجة الإصلاحات** | إزالة استيراد غير مستخدم. |
| 13 | `backend/tests/test_phase10_command_registry.py` | `da62fa45` | **(أ) ضروري نتيجة الإصلاحات** | إزالة استيرادات غير مستخدمة. |
| 14 | `backend/core/capability_registry.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff ومتغيرات غير مستخدمة. |
| 15 | `backend/core/control_request.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 16 | `backend/core/engineering_expansion_contracts.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 17 | `backend/core/generic_planner.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff ومطابقة الأنواع. |
| 18 | `backend/core/planner_schema.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 19 | `backend/core/planner_telemetry.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 20 | `backend/core/session_context.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 21 | `backend/core/tender_contracts.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 22 | `backend/core/workflow_planner.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 23 | `backend/core/workspace_governance_contracts.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff ومواءمة المتغيرات. |
| 24 | `backend/routers/agent_ws.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff غير المستخدمة. |
| 25 | `backend/routers/workflow.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff غير المستخدمة. |
| 26 | `backend/tests/architecture/test_control_request_unification.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 27 | `backend/tests/architecture/test_mutation_authority_gate.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 28 | `backend/tests/architecture/test_phase7_chat_architecture.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 29 | `backend/tests/architecture/test_phase8_workspace_governance_architecture.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 30 | `backend/tests/architecture/test_phase9_engineering_architecture.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 31 | `backend/tests/architecture/test_planner_purity.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 32 | `backend/tests/architecture/test_regex_freeze.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 33 | `backend/tests/architecture/test_removal_gate.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 34 | `backend/tests/architecture/test_tool_schema_deduplication.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 35 | `backend/tests/e2e/test_phase7_chat_control_plane.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 36 | `backend/tests/e2e/test_phase8_gate8_e2e.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 37 | `backend/tests/e2e/test_phase9_engineering_expansion_e2e.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 38 | `backend/tests/e2e/test_phase9b_tender_e2e.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 39 | `backend/tests/intent_suite/test_disambiguation_and_degradation.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 40 | `backend/tests/intent_suite/test_full_pipeline_intent_suite.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 41 | `backend/tests/intent_suite/test_prompt_injection_shield.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 42 | `backend/tests/kernel/test_phase9_engineering_kernels.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 43 | `backend/tests/security/test_track_a_batch_1.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 44 | `backend/tests/test_capability_discovery.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | إزالة استيرادات غير مستخدمة. |
| 45 | `backend/tests/test_contract_conformance.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | إزالة استيرادات غير مستخدمة. |
| 46 | `backend/tests/test_phase8_workspace_governance.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 47 | `backend/tests/test_shared_state.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 48 | `backend/tests/test_track_a_phase1_protocol.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 49 | `backend/tests/test_universal_context.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |
| 50 | `backend/tests/test_ws_wire_contract.py` | `050ffe09` | **(أ) ضروري نتيجة الإصلاحات** | تنظيف استيرادات ruff. |

---

## §4 — الخلاصة والنتيجة
- **إجمالي الملفات المصنفة:** 56 ملفاً (100% من نطاق `aeef7632..49549ba8`).
- **عدد الملفات غير المصنفة:** 0 ملفات (صفر تجاوز نطاق، صفر صفوف غير مصنفة).
- **حالة الثوابت الثلاثة:** مؤكدة وغير ممسوسة 100%.
