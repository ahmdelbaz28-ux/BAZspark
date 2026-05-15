# 🔥 FireAlarmAI - Multi-Domain Building Design Platform

<p align="center">
  <a href="https://docker.com"><img src="https://img.shields.io/badge/Docker-Ready-blue?style=for-the-badge" alt="Docker"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge" alt="Python"></a>
  <a href="https://postgresql.org"><img src="https://img.shields.io/badge/PostgreSQL-14+-blue?style=for-the-badge" alt="PostgreSQL"></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-Web-blue?style=for-the-badge" alt="FastAPI"></a>
  <a href="https://ultralytics.com"><img src="https://img.shields.io/badge/YOLOv8-Vision-red?style=for-the-badge" alt="YOLOv8"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/Status-BETA-orange?style=for-the-badge" alt="Status"></a>
</p>

> AI-powered multi-domain building engineering design platform. Automate Fire Alarm, CCTV, Access Control, Public Address, Data Network, Lighting, and Power system designs in minutes.

---

## 🏗️ Architecture Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                         FireAlarmAI Design Pipeline                                  │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐                   │
│   │   Upload   │ ───▶ │    Vision   │ ───▶ │    Design   │                   │
│   │Floor Plan  │      │   (YOLOv8)  │      │   Engine    │                   │
│   │   Image    │      │   AI Model  │      │  Strategy   │                   │
│   └──────────────┘      └──────────────┘      └──────┬─────┘                   │
│                                                      │                        │
│                                                      ▼                        │
│   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐                   │
│   │   Output    │ ◀───  │  Validation │ ◀─── │   Routing   │                   │
│   │  Generator │      │   Rules     │      │  NetworkX  │                   │
│   │ DWG|PDF|BOQ│      │  NFPA|BM   │      │   Cable    │                   │
│   └──────────────┘      └──────────────┘      └──────────────┘                   │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                              PostgreSQL Database                                   │
│    Projects │ Rooms │ Sessions │ Devices │ Standards │ Manufacturers │ RouteNodes         │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## ⚠️ BETA WARNING - READ BEFORE USE

**⚠️ THIS IS BETA SOFTWARE - NOT FOR PRODUCTION USE**

- All outputs require FPE (Fire Protection Engineer) review
- Not reviewed by licensed engineer yet
- For testing/development only
- See `src/licenses/eula_beta.py` for full license terms

**Lead Engineer**: AhmedElbaz
**Version**: 1.0-BETA
**Date**: 2026-05-15

---

## 🚀 Quick Demo

Start the entire platform with one command:

```bash
# Start FireAlarmAI with Docker
docker-compose -f fire-alarm-db/docker-compose.yml up -d
```

Test the API immediately:

```bash
# Check health and list domains
curl http://localhost:8000/healthz && curl http://localhost:8000/api/domains

# Try the interactive docs
# Open http://localhost:8000/docs in your browser
```
---

## 🎯 How to Use the Interactive Pipeline (v1.0)

The FireAI pipeline now includes **interactive human review** for complete design automation.

### Running the Pipeline

```bash
python3 run_full_pipeline.py <path_to_floor_plan.pdf>
```

### Workflow

1. **Extract rooms** → Unknown types show 0 detectors
2. **Interactive prompt** → Enter room types:
   - `office` → SMOKE detectors
   - `kitchen` → HEAT detectors (SMOKE prohibited)
   - `server_room` → MULTI-CRITERIA detector
   - `bedroom`, `bathroom`, `corridor`, `warehouse`, `storage`, `garage`
   - Press Enter to keep as unknown (no detectors placed)
3. **Final Report** → Detectors placed based on verified types

### Status Meanings

| Status | Meaning |
|--------|---------|
| 🔴 FAILED | Unknown rooms, 0 detectors placed |
| ✅ COMPLETE | All rooms verified, detectors placed |
| ⚠️ PARTIAL | Some rooms verified, others unknown |

### Example

```bash
$ python3 run_full_pipeline.py test_data/hybrid/single_office.pdf
  room_1 (area: 64.3m²) [suggested]: office
  room_2 (area: 36.0m²) [suggested]: kitchen
  room_3 (area: 36.0m²) [suggested]: server_room
  room_4 (area: 36.0m²) [suggested]: 
  ...

✅ DESIGN COMPLETE (AFTER HUMAN REVIEW)
  room_1 → HEAT (3 detectors) ✅
  room_2 → HEAT (2 detectors) ✅
  room_3 → MULTI_CRITERIA (4 detectors) ✅
  room_4 → UNKNOWN (0 detectors) ⚠️
```

### Output Files

- `_FULL_REPORT.json` - Initial analysis with unknowns
- `_FINAL_REPORT.json` - Complete design after human review

### Non-Interactive Mode

```bash
python3 run_full_pipeline.py <file.pdf> --non-interactive
```

Skips human review loop.

---

## 🏢 Engineering Domains

| Domain | Status | Description |
|--------|--------|-------------|
| **FireAlarm** | ✅ Implemented | Smoke/Heat detectors, notification appliances, control panels |
| **CCTV** | ✅ Implemented | IP cameras, PTZ, NVR, corridor/corner placement |
| **PublicAddress** | ✅ Implemented | Ceiling/wall speakers, amplifiers, mass notification |
| AccessControl | 🔄 Planned | Card readers, biometric, door controllers |
| DataNetwork | 🔄 Planned | Switches, routers, access points |
| Lighting | 🔄 Planned | LED panels, emergency lights, occupancy sensors |
| Power | 🔄 Planned | Distribution boards, MCB, RCCB |

> **3 domains fully implemented** with Strategy Pattern engineering logic. More coming Q3-Q4 2026.

---

## 📦 What's Inside

- **Vision Engine**: YOLOv8-powered room detection from floor plans
- **Strategy Pattern**: Swappable engineering logic per domain
- **Auto-Routing**: NetworkX cable path optimization
- **Rule Validation**: NFPA72, BS5839 compliance checking
- **BOQ Generator**: Automatic Bill of Quantities with pricing
- **Multi-Format Output**: DWG, PDF, Excel, JSON exports
- **REST API**: FastAPI with Swagger UI documentation
- **Docker Ready**: One-command deployment

---

## 🛠️ Getting Started

```bash
# Clone the repository
git clone https://github.com/ahmdelbaz28-ux/revit.git
cd revit

# Start with Docker
cd fire-alarm-db && docker-compose up -d

# Or run locally
cd fire-alarm-db/database-design
pip install -r requirements.txt
python main.py

# Open browser
# http://localhost:8000/docs
```

---

## 📚 Documentation

| File | Description |
|------|-------------|
| [fire-alarm-db/README.md](fire-alarm-db/README.md) | Full project README |
| [WHITEPAPER.md](WHITEPAPER.md) | Executive summary & market opportunity |
| [PRICING.md](PRICING.md) | Subscription plans |
| [ROADMAP.md](ROADMAP.md) | Development roadmap |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for adding new domains and contributing to the project.

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Made with ❤️ by FireAlarmAI Team</strong>
</p>