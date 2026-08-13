# First Fire Alarm Design

This tutorial walks you through designing a fire alarm system for a simple office building using BAZSpark. You will learn how to:

1. Create a project
2. Define room geometry
3. Place smoke detectors per NFPA 72
4. Verify compliance
5. Generate a report

## Prerequisites

- BAZSpark backend running (see [Installation](../how-to/installation.md))
- API key configured
- Basic understanding of NFPA 72 (helpful but not required)

---

## Step 1: Create a Project

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Office Building - Floor 1",
    "description": "Fire alarm design for first floor",
    "author": "Your Name"
  }'
```

Response:

```json
{
  "id": "proj_abc123",
  "name": "Office Building - Floor 1",
  "status": "created"
}
```

Save the project ID — you will need it for subsequent steps.

---

## Step 2: Define a Room

```bash
curl -X POST http://localhost:8000/api/v1/projects/proj_abc123/elements \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "room",
    "name": "Open Office",
    "geometry": {
      "width": 15.0,
      "length": 20.0,
      "ceiling_height": 3.0
    },
    "occupancy_type": "business"
  }'
```

Response:

```json
{
  "id": "elem_def456",
  "type": "room",
  "name": "Open Office",
  "area_sqm": 300.0
}
```

---

## Step 3: Calculate Smoke Detector Spacing

```bash
curl -X POST http://localhost:8000/api/v1/qomn/smoke-spacing \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "room_width": 15.0,
    "room_length": 20.0,
    "ceiling_height": 3.0,
    "occupancy_type": "business"
  }'
```

Response:

```json
{
  "spacing_m": 9.1,
  "coverage_radius_m": 6.37,
  "detectors_needed": 6,
  "coverage_percentage": 98.5,
  "compliant": true,
  "reference": "NFPA 72-2022 §17.7.3.2.3"
}
```

**What this means:**

- **Spacing: 9.1m** — Maximum spacing per NFPA 72 §17.7.3.2.3
- **Coverage radius: 6.37m** — Each detector covers a 6.37m radius (0.7 × 9.1m)
- **Detectors needed: 6** — Minimum number for this room
- **Coverage: 98.5%** — Percentage of room area covered
- **Compliant: true** — Meets NFPA 72 requirements

---

## Step 4: Verify Compliance

```bash
curl -X POST http://localhost:8000/api/v1/qomn/compliance \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "proj_abc123",
    "element_id": "elem_def456"
  }'
```

Response:

```json
{
  "compliant": true,
  "checks": [
    {
      "rule": "NFPA 72 §17.7.3.2.3",
      "description": "Smoke detector spacing",
      "status": "pass",
      "detail": "Spacing 9.1m ≤ maximum 9.1m"
    },
    {
      "rule": "NFPA 72 §17.7.3.2.4",
      "description": "Ceiling height limit",
      "status": "pass",
      "detail": "Height 3.0m ≤ maximum 18.288m"
    },
    {
      "rule": "NFPA 72 §17.7.4.2.3.1",
      "description": "Coverage percentage",
      "status": "pass",
      "detail": "Coverage 98.5% ≥ minimum 95%"
    }
  ]
}
```

---

## Step 5: Generate a Report

```bash
curl -X POST http://localhost:8000/api/v1/reports/generate \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "proj_abc123",
    "type": "compliance",
    "format": "pdf"
  }'
```

The report includes:
- Project details
- Room geometry
- Detector placement
- Compliance verification results
- HMAC-signed audit trail

---

## What You Learned

1. **Project creation** — Organizing your design work
2. **Room definition** — Specifying geometry and occupancy
3. **Detector spacing** — Applying NFPA 72 formulas
4. **Compliance verification** — Automated code checking
5. **Report generation** — Documenting your design

## Next Steps

- Add multiple rooms and floors
- Include walls and openings
- Design notification appliance circuits (NAC)
- Calculate voltage drop and battery sizing
- Export to AutoCAD or Revit

## References

- [API Reference](../reference/api-reference.md) — All endpoints
- [Engineering Formulas](../reference/engineering-formulas.md) — NFPA 72 constants
- [Architecture](../reference/architecture.md) — System design
