# Canonicalization Functor Layer (CFL) v2.0

## 0. المبدأ السيادي
There is only one semantic truth space; all other CAD systems are projections into it, not peers of it.

Revit = Canonical BIM Ontology (Authority Anchor).
All other CAD = Projection Spaces only.

## 1. هيكل الطبقات الثلاث (Three-Layer Architecture)

### Layer 1: Parsing Layer (Syntactic Ingestion)
- يستقبل بيانات خام من أي CAD (AutoCAD, Rhino, ArchiCAD)
- يستخرج إحداثيات، طبقات، بلوكات
- لا يقوم بأي تفسير دلالي
- Output: RawGeometricFragments

### Layer 2: Interpretation Layer (Semantic Hypothesis Generation)
- يحاول matching مع الأنطولوجيا المعتمدة
- يستخدم probabilistic ontology alignment
- يولد فرضيات دلالية مع درجة ثقة (Confidence Score 0-100%)
- Output: CandidateSemanticFragments + ConfidenceScore

### Layer 3: Canonicalization Layer (Truth Fixation)
- يطبق Π_cad على CandidateSemanticFragments
- يرفض، يقبل، أو يعزل
- Output: CanonicalFragment أو QuarantineRecord

## 2. مقياس الفقد الدلالي (Graduated Semantic Loss Metric)

SLM = عدد العناصر غير المعترف بها / إجمالي العناصر

| SLM Range | Action |
|-----------|--------|
| SLM < 5% | ✅ ACCEPT (minimal loss) |
| SLM 5% - 20% | ⚠️ QUARANTINE (human validation required) |
| SLM > 20% | ❌ REJECT (unacceptable ambiguity) |

لا يوجد "اجتهاد" في السلامة. Quarantine تعني: لا يُصدر إثبات حتى يراجع بشري.

## 3. دالة الإسقاط (Π_cad)
Π_cad: CAD_Geometry → Option<CanonicalFragment>
- تعيد None إذا انخفضت درجة الثقة عن 95% (أو SLM > 20%)

## 4. الأنطولوجيا كمخطط بياني (Typed Ontology Graph)
- Nodes: Canonical Entities (SmokeDetector, HeatDetector, ManualCallPoint, FireDoor, SolidWall, MerkleZone)
- Edges: Allowed Semantic Transformations (e.g., "translates_to", "blocks_path_of")
- Mapping: Functorial alignment بين الـ CAD geometry والـ Canonical Graph

لا يُستخدم قاموس ثابت (Static Dictionary)، بل Ontology Graph يمكن تمديده عبر إضافة Nodes/Edges جديدة بموجب Governance Process.

## 5. قواعد التحويل الحتمي (Canonical Serialization)
- جميع الإحداثيات تُقرب إلى 6 خانات عشرية
- المصفوفات تُفرز أبجدياً قبل الهاش
- أي عنصر بدون دلالة كاملة يُسجل في SLM
- Quarantine records تُوقع بختم SHA256 أيضاً

## 6. التوافق مع المعمارية المجمدة
- CFL يعمل كطبقة وسيطة بين المصادر غير البيمية (AutoCAD) و SEL/GEL
- لا يعدل SEL أو GEL
- لا يغير الأنطولوجيا الأساسية (Revit/BIM)
- يلتزم بالـ Architecture Freeze