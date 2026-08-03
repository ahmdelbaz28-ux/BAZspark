<div align="center">

# 🔥 BAZspark

### **Safety-Critical Fire Alarm Engineering & Digital Twin Platform**
*منصة هندسة أنذار الحريق الذكية والتوأم الرقمي القياسي*

[![CI/CD Status](https://github.com/ahmdelbaz28-ux/BAZspark/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ahmdelbaz28-ux/BAZspark/actions/workflows/ci.yml)
[![NFPA Compliance](https://img.shields.io/badge/Standard-NFPA%2072--2022-red.svg)](https://www.nfpa.org/codes-and-standards/all-codes-and-standards/list-of-codes-and-standards/detail?code=72)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.55.0-orange.svg)](VERSION)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.138%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18.3.1-61DAFB.svg)](https://react.dev/)

---

### 🌐 Live Environments / الروابط المباشرة للنظام

[![Frontend Demo](https://img.shields.io/badge/🚀%20Web%20App-ba--zspark.vercel.app-blueviolet?style=for-the-badge&logo=vercel)](https://ba-zspark.vercel.app)
&nbsp;&nbsp;&nbsp;&nbsp;
[![Backend API Docs](https://img.shields.io/badge/⚡%20API%20Engine-ahmdelbaz28--bazspark.hf.space-emerald?style=for-the-badge&logo=huggingface)](https://ahmdelbaz28-bazspark.hf.space)

---

![BAZspark Platform Banner](docs/assets/screenshots/banner-dashboard.png)

</div>

---

## 📌 1. Executive Summary & Core Mission | نبذة تنفيذية والهدف الأساسي

**BAZspark** is a state-of-the-art, safety-critical fire protection engineering platform engineered to automate compliance verification, voltage drop calculations, battery backup capacity sizing, and bidirectional CAD/BIM drawing translation according to **NFPA 72-2022** and **SOLAS Marine** safety codes.

By coupling a **deterministic mathematical calculation engine** with an **AI-assisted Digital Twin**, BAZspark eliminates human drafting errors, accelerates MEP approval cycles, and produces an immutable, Merkle-tree signed audit trail for every design decision.

---

## 📸 2. Interactive Product Tour | جولة تفاعلية بالصور الشاشية

<div align="center">

### 🖥️ Main Engineering Dashboard & System Monitoring
*لوحة التحكم الرئيسية وإدارة المشاريع الهندسية*
![BAZspark Dashboard](docs/assets/screenshots/dashboard.png)

---

### 🎨 Fire Alarm Canvas & CAD Designer
*محرر المخططات التفاعلي لتوزيع الحساسات وأجراس الإنذار*
![Fire Alarm Canvas Designer](docs/assets/screenshots/fire-alarm-designer.png)

---

<table width="100%">
<tr>
<td width="50%" align="center">
<b>🏢 Digital Twin (AutoCAD ↔ Revit Bridge)</b><br/>
<i>التوأم الرقمي للتحويل المباشر بين المخططات والـ BIM</i><br/><br/>
<img src="docs/assets/screenshots/digital-twin.png" alt="Digital Twin Engine" width="100%"/>
</td>
<td width="50%" align="center">
<b>⚡ Compliance & NFPA 72 Verification Center</b><br/>
<i>مركز تحقق الملاءمة الهندسية ومعايير NFPA 72</i><br/><br/>
<img src="docs/assets/screenshots/compliance-center.png" alt="Compliance Center" width="100%"/>
</td>
</tr>
<tr>
<td width="50%" align="center">
<b>📊 BoQ, Bill of Materials & Export Center</b><br/>
<i>إخراج جداول الكميات وتصدير التقارير الهندسية</i><br/><br/>
<img src="docs/assets/screenshots/reports.png" alt="Reports & BoQ" width="100%"/>
</td>
<td width="50%" align="center">
<b>🛠️ Multi-Loop Engineering Workspace</b><br/>
<i>مساحة عمل المهندس لحسابات الجهد والبطاريات</i><br/><br/>
<img src="docs/assets/screenshots/engineering-workspace.png" alt="Engineering Workspace" width="100%"/>
</td>
</tr>
</table>

---

### ✅ Quality Assurance & Verification Gates
*بوابات الفحص والتأكد الذاتي من صحة الحسابات والأمان (100% Pass)*
![Quality Gates Green](docs/assets/screenshots/all-gates-green.png)

</div>

---

## 👥 3. Who is BAZspark For? | لمن صُمم هذا النظام؟

| Target User / المستخدم المستهدف | Primary Use Case / حالات الاستخدام الرئيسية | Core Benefit / الفائدة المحققة |
|---|---|---|
| 👷 **Fire Protection Engineers**<br/>*(مهندسو الوقاية من الحريق)* | Automating NFPA 72 detector coverage, visual candela calculations, NAC loop voltage drop, and 24h/60m battery backup sizing. | Eliminates manual Excel calculation errors and guarantees 100% code compliance. |
| 🏛️ **MEP & BIM Consultants**<br/>*(استشاريو ومصممو BIM)* | Bidirectional conversion between AutoCAD DWG files and Autodesk Revit BIM models with IFC 4.3 compatibility. | Saves up to 80% of drafting time by converting 2D drawings into native BIM elements. |
| 🛡️ **Authorities Having Jurisdiction (AHJ)**<br/>*(الجهات الرقابية وهئية الدفاع المدني)* | Reviewing submitted fire alarm designs using verifiable Merkle-tree signed audit reports. | Instant calculation transparency with zero ambiguity or unverified assumptions. |
| 💻 **Developers & Integrators**<br/>*(المطورون ومهندسو الأنظمة)* | Integrating custom CAD tools, IoT fire panels, and BIM software using 247+ OpenAPI REST & WebSocket endpoints. | Fully async, high-performance Python 3.8+ & React 18 architecture. |

---

## 📐 4. System Architecture & Engineering Composition | التكوين الهندسي والمعماري

BAZspark follows a decoupled, asynchronous micro-architecture ensuring that calculation logic remains isolated from presentation layers:

```
                                  ┌───────────────────────────────────────────────────────────┐
                                  │   React 18 + TypeScript 5.9 + Vite 8 + Tailwind CSS 4     │
                                  │   Interactive HTML5 Canvas │ Dashboard │ Real-time Stream │
                                  └─────────────────────────────┬─────────────────────────────┘
                                                                │ REST APIs + WebSockets
                                  ┌─────────────────────────────▼─────────────────────────────┐
                                  │          FastAPI 0.138+ Asynchronous Backend Engine       │
                                  │   247+ Endpoints │ HMAC-SHA256 Auth │ SSRF Guard │ RBAC    │
                                  └──────┬──────────────────────┬──────────────────────┬──────┘
                                         │                      │                      │
                   ┌─────────────────────▼──────┐    ┌──────────▼───────────┐    ┌─────▼──────────────────────┐
                   │ NFPA 72 Calculation Engine │    │ Digital Twin Kernel  │    │ Unified Storage Infrastructure│
                   │ • Voltage Drop & End of Line│    │ • AutoCAD Bridge     │    │ • PostgreSQL (Primary DB)  │
                   │ • Battery Backup Capacity  │    │ • Revit BIM Adapter  │    │ • SQLite WAL (Local)       │
                   │ • Sound & Strobe Coverage  │    │ • DXF/DWG/IFC Parser │    │ • Redis & Qdrant Vector    │
                   └────────────────────────────┘    └──────────────────────┘    └────────────────────────────┘
```

### 🧩 Core Component Layers

1. **Deterministic Calculation Core (`fireai/`, `qomn_fire/`)**:
   - **Voltage Drop Solver**: Exact Kirchhoff circuit analysis for Notification Appliance Circuits (NAC) per NFPA 72 §10.6.7.
   - **Battery Capacity Sizer**: Computes required Ampere-Hours ($Ah$) for 24-hour standby + 5/60-minute alarm modes with 20% safety factor.
   - **Acoustic & Visual Coverage**: Determines indoor/outdoor strobe candela requirements and speaker dBA attenuation.

2. **Digital Twin Engine (`autocad_addin/`, `parsers/`)**:
   - High-throughput DXF, DWG, IFC 4.3, and PDF floorplan parser.
   - Bidirectional C# .NET bridge linking AutoCAD and Revit elements in real time.

3. **Security & Audit Governance (`backend/auth.py`, `backend/rbac.py`)**:
   - Strict Role-Based Access Control (RBAC) with 6 permission levels.
   - Merkle-tree cryptographic signature for every calculation snapshot.

---

## ⚡ 5. How to Use BAZspark | كيفية الاستخدام والتشغيل السريع

### 📋 Prerequisites | المتطلبات الأساسية
- **Python**: `3.8.4` or higher
- **Node.js**: `22.0.0` or higher (`npm 11+`)
- **Git**: `2.40+`

---

### 🚀 Step 1: Clone & Setup Backend | إعداد الخلفية

```bash
# 1. Clone the repository
git clone https://github.com/ahmdelbaz28-ux/BAZspark.git
cd BAZspark

# 2. Install backend dependencies
pip install -e ".[dev,parsing]"

# 3. Set environment secrets & launch API server
export FIREAI_API_KEY="your-secure-api-key"
export FIREAI_SESSION_SECRET=$(python3 -m backend.session_secret generate | tail -1)

uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```
> The API documentation will be available at `http://127.0.0.1:8000/docs`.

---

### 🎨 Step 2: Setup & Launch Frontend | إعداد الواجهة الرسومية

```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm ci

# Start Vite development server
npm run dev
```
> Access the web application at `http://localhost:5173`. Navigate to **Settings** and input your `FIREAI_API_KEY`.

---

### 🐳 Step 3: Run via Docker | التشغيل الحاوي باستخدام Docker

```bash
# Build and run entire stack with Docker Compose
docker-compose up -d --build
```

---

## 🔬 6. Verification & Quality Enforcement | فحوصات الجودة والتحقق

BAZspark enforces strict automated Quality Gates before any pull request is merged:

```bash
# Run unit and security test suites (145+ tests)
python -m pytest tests/test_ssrf_and_security_protocol.py tests/test_security.py backend/tests/test_database_and_utils.py

# Run static linter analysis
python -m ruff check .
```

---

## 📄 7. License & Governance | الترخيص والتطوير

BAZspark is open-source software licensed under the **[MIT License](LICENSE)**.

Developed and Maintained by **Eng. Ahmed Elbaz**.

---
<div align="center">
<b>BAZspark Engine © 2026 | Safety-Critical Fire Protection Engineering</b>
</div>