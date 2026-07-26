# BAZSpark / FireAI — Domain Glossary

> **Purpose:** Precise definitions of domain terms used across the BAZSpark
> codebase. This is a glossary — it documents concepts, not implementation.
> When a term is ambiguous or overloaded, this file resolves which meaning
> applies where.

---

## A — Architectural & Project Concepts

### BIM (Building Information Modeling)
A digital representation of a building's physical and functional
characteristics. In this project, BIM is the *input model* (typically from
Revit or IFC) that the engineering calculations operate on.

**Distinguished from:** *Digital Twin* — BIM is a static design model;
Digital Twin is a live system connected to real-world data.

### Digital Twin
A live, bidirectional digital representation of a physical building or
system that is updated with real-world sensor data and can actuate changes.
The Digital Twin is the overarching system; BIM (Revit/IFC) is one input
source.

**Distinguished from:** *BIM* — static design model vs. live operational model.

### Project
An engineering design project containing devices, connections, elements,
and engineering calculations. Persisted as a database entity, synced to
UDM for conflict detection.

### UDM (Universal Data Model)
**System B** database (`udm_elements.db`). A secondary, synchronized
data store used for conflict detection and spatial analysis. Not the
primary record — data originates in the primary database and is synced
to UDM via `project_bridge.py`.

**Distinguished from:** *Digital Twin database* — System A (`digital_twin.db`)
is the primary database; UDM is a synced copy for spatial queries.

---

## B — Engineering Domain

### FACP (Fire Alarm Control Panel)
The central control unit of a fire alarm system. Per NFPA 72, the FACP
receives signals from initiating devices (detectors, pull stations) and
activates notification appliances (horns, strobes).

### NAC (Notification Appliance Circuit)
The circuit that powers visible and audible notification appliances
(strobes, horns, speakers). NAC design must meet NFPA 72-2022 §18.5
candela and spacing requirements.

### NFPA 72
National Fire Alarm and Signaling Code — the primary standard enforced
by this platform. All engineering calculations reference specific NFPA 72
sections (e.g., §17.7.3.2.3 for smoke detector spacing).

**Canonical source:** `fireai/constants/nfpa72.py`

### QOMN
The deterministic engineering kernel that performs NFPA 72 calculations
(smoke spacing, heat spacing, battery capacity, voltage drop, detector
placement). The name is an internal project codename; the engine is
also referred to as **QOMN-FIRE**.

**Sub-systems:**
- `qomn_fire/` — Core computational engine (placement, routing, panel selection)
- `qomn_conduit/` — Conduit routing and fill analysis
- `QOMNKernel` (in `fireai/core/qomn_kernel.py`) — Python interface

### SLD (Single Line Diagram)
A simplified schematic of an electrical power system. Used in the
engineering UI for visualizing power distribution.

---

## C — CAD / BIM Integration

### AutoCAD
Autodesk CAD software used for 2D/3D drafting. The backend integrates
via named-pipe bridge (Windows) or simulation mode. Primarily reads DWG
and DXF files.

### Revit
Autodesk BIM authoring tool. Integration is via Revit API (Windows) or
simulation. Reads/writes RVT files, synchronizes BIM elements with the
Digital Twin.

### IFC (Industry Foundation Classes)
Vendor-neutral BIM exchange format (ISO 16739). Used for headless (no
Revit/AutoCAD) BIM processing.

### DXF / DWG
AutoCAD drawing formats. DXF is the open exchange format; DWG is the
native binary format. Supported via LibreDWG and custom converters.

**Parsing pipeline:** `incoming file → parsers/ → qomn_fire/parsers/ → QOMN kernel`

---

## D — Core Entities (Beware: Overloaded Terms)

These terms have **different meanings** in different contexts. Pay attention
to which layer you're in.

### Device (⚠️ 3 meanings)

| Context | Meaning | Example |
|---------|---------|---------|
| Frontend canvas (`DeviceType`) | Electrical power system component | GENERATOR, BATTERY, LOAD, PANEL |
| Backend `db_models.py` | Fire alarm field device | smoke detector, heat detector, pull station, notification appliance |
| Backend `schemas.py` | UDM CRUD entity | generic device record in the elements database |

**Rule of thumb:** If it has a `defaultLoad` (Amperes), it's a power
device on the engineering canvas. If it has NFPA 72 compliance data
(spacing, coverage), it's a fire alarm device. If it's synced to UDM
via `sync_device_to_udm()`, it's a UDM entity.

### Element (⚠️ 3 meanings)

| Context | Meaning | Example |
|---------|---------|---------|
| Frontend `CanvasElement` | Interactive object on the engineering canvas | drag-and-drop device icon |
| Backend `schemas.py` `Element` | Building element with geometry (UDM entity) | wall, door, room |
| Backend `UniversalElement` | Frozen dataclass in the multi-db service | generic element with relationships |

### Connection (⚠️ 2 meanings)

| Context | Meaning |
|---------|---------|
| Frontend / Backend `Connection` | Cable or conduit link between two devices |
| Backend `Element.relationships` | Semantic relationship between building elements |

---

## E — Security & Infrastructure

### Session
An authenticated user session, identified by a cryptographically random
session ID (256 bits), signed with HMAC-SHA256, and stored as an
HttpOnly, SameSite=Strict, `__Host-` prefixed cookie.

### API Key
A bearer token used for server-to-server authentication. Validated via
bcrypt against the API key store. Distinguished from session auth
(cookie-based, browser-facing).

### RBAC (Role-Based Access Control)
Authorization model with roles (ADMIN, ENGINEER, VIEWER, etc.) and
permissions (e.g., `qomn:read`, `qomn:execute`). Enforced at the
endpoint level via `require_permission()` dependencies.

### Correlation ID
A UUID propagated through request context (`X-Correlation-ID` header)
for end-to-end tracing across services. Required for NFPA 72 §14.2.4
audit trail compliance.

### Audit Trail
Tamper-evident (HMAC-SHA256 signed) log of safety-critical operations.
Supports NFPA 72 compliance and AHJ (Authority Having Jurisdiction) review.

---

## F — Known Documentation Contradictions

The following claims in `ARCHITECTURE.md` are **not supported** by the
current codebase:

| Claim in ARCHITECTURE.md | Reality |
|--------------------------|---------|
| "GraphQL API" | No GraphQL implementation exists — all APIs are REST (FastAPI) |
| "Celery" for task queuing | No Celery dependency or implementation exists |
| "Mobile App" | No mobile app code exists in this repository |
| "Leaflet" for map visualization | No Leaflet dependency found in frontend |

These items may reflect aspirational architecture or have been removed
during refactoring. The documentation should be updated to match the
actual implementation.
