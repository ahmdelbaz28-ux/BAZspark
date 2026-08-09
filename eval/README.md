# BAZspark RAG Evaluation — دليل التشغيل الكامل

> **المهارة المستخدمة:** `rag-eval` (NVIDIA RAG Blueprint — v2.6.0)  
> **المشروع:** BAZspark — NFPA 72-2022 Fire Alarm Design Intelligence Platform  
> **المؤلف:** Ahmed Elbaz

---

## الهدف

قياس جودة إجابات **مساعد الذكاء الاصطناعي الهندسي** (Engineering Copilot / GraphRAG Engine) في مشروع BAZspark على أسئلة NFPA 72 الهندسية، باستخدام معايير RAGAS الثلاثة:

| المعيار | المعنى |
|---------|---------|
| `nv_accuracy_mean` | دقة الإجابة مقارنةً بالإجابة المرجعية |
| `nv_context_relevance_mean` | مدى صلة السياق المسترجع بالسؤال |
| `nv_response_groundedness_mean` | مدى استناد الإجابة إلى السياق المسترجع |

---

## هيكل مجموعة البيانات

```
eval/
└── nfpa72_rag_dataset/
    ├── corpus/                              ← وثائق NFPA 72 المرجعية
    │   ├── NFPA72_chapter17_smoke_detectors.txt
    │   ├── NFPA72_chapter17_heat_detectors.txt
    │   ├── NFPA72_chapter24_notification_appliances.txt
    │   ├── NFPA72_voltage_drop_formulas.txt
    │   └── BAZspark_system_overview.txt
    └── train.json                           ← 30 سؤالاً هندسياً بإجاباتها
```

---

## المتطلبات

```bash
# Python 3.11+
python --version

# uv (مُدير الحزم)
uv --version

# تثبيت متطلبات التقييم
uv sync --project scripts/eval

# مفتاح RAGAS (اختر واحداً)
$env:NVIDIA_API_KEY = "your-nvidia-api-key"   # PowerShell
$env:OPENAI_API_KEY  = "your-openai-api-key"  # PowerShell بديل
```

---

## التشغيل السريع

### 1. التحقق من صحة مجموعة البيانات

```bash
python scripts/eval/prepare_dataset.py validate eval/nfpa72_rag_dataset
```

**الإخراج المتوقع:**
```
[OK]   corpus/ found with 5 file(s)
[OK]   train.json is a valid array with 30 row(s)
[OK]   All required fields present. Dataset is valid.
```

### 2. تشغيل التقييم (dry-run — بدون خادم RAG)

```bash
python scripts/eval/evaluate_rag.py \
  --dataset-paths eval/nfpa72_rag_dataset \
  --host localhost \
  --port 8000 \
  --dry_run
```

### 3. تشغيل التقييم الكامل (مع خادم BAZspark)

```bash
# تشغيل BAZspark API أولاً
uvicorn fireai.core.fireai_api:app --host 0.0.0.0 --port 8000 &

# تشغيل التقييم
python scripts/eval/evaluate_rag.py \
  --dataset-paths eval/nfpa72_rag_dataset \
  --host localhost \
  --port 8000 \
  --output_dir results \
  --top_k 5 \
  --vdb_top_k 20 \
  --temperature 0.0
```

### 4. عرض ملخص النتائج

```bash
python -m json.tool results/nfpa72_rag_dataset/rag_nfpa72_rag_dataset_evaluation_summary.json
```

### 5. تحليل النتائج

```bash
# جدول أسوأ الأسئلة دقةً
python scripts/eval/analyze_results.py \
  --dataset nfpa72_rag_dataset \
  --top-n 10

# تصدير CSV
python scripts/eval/analyze_results.py \
  --dataset nfpa72_rag_dataset \
  --export-csv

# تقرير Markdown للـ PR
python scripts/eval/analyze_results.py \
  --dataset nfpa72_rag_dataset \
  --markdown \
  --save-markdown docs/rag_eval_report.md
```

---

## مقارنة الإعدادات (Quality Sweeps)

```bash
# Baseline — بدون reranker
python scripts/eval/evaluate_rag.py \
  --dataset-paths eval/nfpa72_rag_dataset \
  --host localhost --port 8000 \
  --skip_ingestion \
  --disable_reranker \
  --temperature 0.0 \
  --output_dir results/baseline_no_rerank

# مع Reranker — مقارنة الأداء
python scripts/eval/evaluate_rag.py \
  --dataset-paths eval/nfpa72_rag_dataset \
  --host localhost --port 8000 \
  --skip_ingestion \
  --enable_reranker \
  --temperature 0.0 \
  --output_dir results/with_rerank
```

---

## مخرجات التقييم

| الملف | المحتوى |
|-------|---------|
| `rag_<label>_evaluation_data.json` | نتائج كل سؤال: السؤال، الإجابة المرجعية، الإجابة المُولّدة، السياق |
| `rag_<label>_evaluation_summary.json` | متوسطات RAGAS الثلاثة |
| `rag_<label>_evaluation_results.json` | قيم RAGAS لكل سؤال على حدة |
| `rag_<label>_evaluation_metrics.json` | تقرير هيكلي شامل |

---

## التكامل مع CI/CD

يُشغَّل `.github/workflows/rag-eval.yml` تلقائياً عند التغيير في:
- `fireai/infrastructure/graphrag_engine.py`
- `eval/nfpa72_rag_dataset/**`
- `scripts/eval/**`

**عتبة الجودة:** `nv_accuracy_mean ≥ 0.75` — يفشل الـ CI إذا انخفض عنها.

---

## تشخيص الأخطاء

| الخطأ | السبب | الحل |
|-------|-------|------|
| `NVIDIA_API_KEY` غير موجود | RAGAS لا يستطيع التشغيل | اضبط المفتاح في البيئة أو اعمل dry-run |
| `train.json must be a JSON array` | شكل JSON خاطئ | تحقق باستخدام `prepare_dataset.py validate` |
| `generated_contexts` فارغة | فجوة في الاسترجاع | افحص collection، top_k، حالة الـ ingestor |
| `Failed to get response from rag-server` | الخادم غير متاح | تأكد من تشغيل BAZspark API على المنفذ المحدد |

---

## إضافة مجموعة بيانات جديدة

```bash
# من ملف CSV
python scripts/eval/prepare_dataset.py from-csv source.csv \
  --question-col question \
  --answer-col answer \
  --output-dir eval/my_new_dataset

# أضف وثائق الـ corpus
mkdir eval/my_new_dataset/corpus
cp my_docs/*.txt eval/my_new_dataset/corpus/

# تحقق من البيانات
python scripts/eval/prepare_dataset.py validate eval/my_new_dataset
```

---

## المراجع

- [rag-eval SKILL.md](.agents/skills/rag-eval/SKILL.md)
- [dataset-and-conversion.md](.agents/skills/rag-eval/references/dataset-and-conversion.md)
- [benchmark-execution.md](.agents/skills/rag-eval/references/benchmark-execution.md)
- [result-analysis.md](.agents/skills/rag-eval/references/result-analysis.md)
- [NVIDIA_RAG_BLUEPRINT_EVALUATION.md](docs/NVIDIA_RAG_BLUEPRINT_EVALUATION.md)
