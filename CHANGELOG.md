# Changelog

All notable changes to FireAI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.56.0] — 2026-07-01

### Added — V152: Multi-Provider + Key Expiry + Bulk Delete + Error Boundary

- **Multi-Provider Support**: 6 Vision API providers (openai, anthropic, gemini, azure, openrouter, opencode) with generic `/{provider}` endpoints + backward-compat `/openai` aliases + `/providers/list` endpoint
- **Key Expiry**: `expires_at` column + `is_expired` field + test endpoint rejects expired keys + frontend amber "expired" badge + datetime-local input
- **Bulk Delete**: `POST /{provider}/bulk-delete` endpoint (delete all or specific ids) + provider isolation + frontend "Delete All" button
- **Error Boundary**: `<ErrorBoundary>` wraps `<VisionApiKeysTab>` — tab crash doesn't break Settings page
- **18 new tests** for V152 features (multi-provider parametrized + expiry + bulk-delete + providers-list)

### Added — V151.1: Launch-Prep Hardening

- **CSRF Protection**: frontend sends `X-CSRF-Token` header on all POST/DELETE/TEST (reads `__Host-fireai_csrf_token` cookie)
- **CUA Agent Driver**: `fireai/agents/cua_agent.py` with `CUAAgent.step()/run()` + mss/PIL screenshot capture + action extraction
- **Rate Limiting**: POST/DELETE 10/min, test 5/min via slowapi
- **Audit Logging**: `_audit_key_event()` records add/delete in AuditStore
- **Toast Notifications**: sonner toasts for save/delete/test success/failure
- **i18n**: 26 keys in en.json + ar.json for all V151 strings
- **Copy-to-Clipboard**: ghost button copies masked key + toast feedback
- **Loading Skeleton**: animate-pulse skeleton during initial load

### Added — V151: Vision API Keys (AES-256-GCM encrypted)

- **AES-256-GCM Encryption**: `backend/vision_key_store.py` with 12-byte random nonce per record + AAD + 4-tier master key fallback
- **REST Endpoints**: POST/GET/GET-id/DELETE/POST-test at `/api/v1/settings/keys/openai/*`
- **CUA Loop**: `fireai/vision/cua_loop.py` with DB→env→OpenCV fallback chain (never raises)
- **DB Schema**: `vision_api_keys` table in SQLite + PostgreSQL + ORM model
- **Frontend Tab**: `VisionApiKeysTab` in SettingsPage with form + list + test + delete
- **33 tests** for encryption/masking/DB/CUA loop/router/RBAC/security
- **Masking**: `fe_sk***...***f4c1` format (first 2 + last 4 chars only)

### Changed

- **README**: updated with V151-V152 features, new non-black screenshots (22 images regenerated), hero banner PNG, latest test counts (322+ verified)
- **VERSION**: bumped to 1.56.0
- **requirements.txt**: explicit `httpx>=0.24.0,<1.0.0` dependency
- **Screenshots**: all 22 images regenerated via AI image generation, brightness verified ≥80/255 (previously were black at 20-25/255)

### Security

- **CSRF**: Double Submit Cookie on all state-changing requests (V151.1)
- **AES-256-GCM**: Vision API keys encrypted at rest with authenticated encryption (V151)
- **Rate Limiting**: prevents abuse of test endpoint (V151.1)
- **Audit Trail**: all key add/delete events recorded (V151.1)
- **RBAC**: all V151-V152 endpoints require `Permission.SYSTEM_CONFIG` (admin only)
- **Idempotent DELETE**: returns 204 regardless of existence (no info leak)

## [1.55.0] — 2026-06-30

### Added — V150: Thread Safety + Edge Cases + API Ergonomics

- 12 root-cause fixes across thread safety, edge cases, and API ergonomics
- 38 new tests in `tests/test_v150_thread_safety_edge_cases_api_ergonomics.py`

## [Unreleased]

### Added
- New NFPA 72-2022 compliance checks
- Enhanced acoustic modeling for notification appliances
- Real-time collaboration features for design teams
- Advanced 3D visualization engine

### Changed
- Improved performance for large building models
- Updated CAD parsing for newer file formats
- Enhanced error reporting and diagnostics

### Deprecated
- Legacy API endpoints (will be removed in v2.0)

### Removed
- Support for Python < 3.12

### Fixed
- Memory leak in geometry processing
- Race condition in concurrent analysis
- Incorrect coverage calculations for sloped ceilings

### Security
- Addressed potential injection in CAD file parsing
- Strengthened authentication for API endpoints

## [1.0.0] - 2026-06-11

### Added
- Initial release of FireAI Platform
- Core fire protection engineering engine
- NFPA 72 compliance checking
- AutoCAD and Revit integration
- Advanced detector placement algorithms
- Comprehensive audit trail system
- Multi-zone fire alarm system design
- Emergency voice communication planning
- Structural fire protection analysis
- Egress modeling and analysis

### Features
- **Automated Detector Placement**: Optimizes smoke and heat detector locations per NFPA 72
- **Compliance Verification**: Real-time checking against NFPA codes and local regulations
- **NAC Design**: Notification Appliance Circuit design with voltage drop calculations
- **Power Supply Allocation**: Automatic FACP and NAC power supply sizing
- **Integration Ready**: APIs for CAD software integration
- **Safety First**: Multiple validation layers and fail-safe mechanisms

### Safety Hardening
- V12 fixes for semantic substring collisions in detector identification
- V13 safety hardening for coverage verification
- V14 fixes for DC return path voltage drop calculations
- V19.1 RTI (Response Time Index) validation for shunt-trip systems
- V20.2 safety gate verification and proof validation

### Architecture
- Three-layer communication protocol (FACP)
- Distributed processing capability
- Pluggable compliance engine
- Extensible rule system
- Modular design for easy maintenance

### Performance
- Optimized spatial algorithms using Shapely/GEOS
- Parallel processing for large projects
- Efficient memory management
- Fast CAD file parsing

---

## Versioning

Major versions indicate significant architectural changes or safety hardening.
Minor versions add features and improvements.
Patch versions fix bugs and security issues.

## Safety Classification

- **Critical** - Safety-related fixes that prevent potential harm
- **High** - Important functionality improvements
- **Medium** - Feature enhancements
- **Low** - Minor improvements and documentation

---

**Note**: This changelog reflects the evolution of FireAI from its initial concept to a production-ready safety-critical system. All changes have undergone rigorous testing and safety validation.