# Datapuff API Endpoints Reference Guide

**Generated:** 2026-07-30  
**Total Endpoints:** 85  
**Services:** 11  
**API Version:** 1.0.0  
**RBAC Version:** 3-role (admin, engineer, viewer)

---

## Table of Contents

1. [Service Overview](#service-overview)
2. [Authentication Patterns](#authentication-patterns)
3. [Standard Error Response Format](#standard-error-response-format)
4. [Service Dependency Map](#service-dependency-map)
5. [Versioning Strategy](#versioning-strategy)
6. [Base URLs](#base-urls)
7. [Complete Endpoint List](#complete-endpoint-list)
8. [Statistics](#statistics)

---

## Service Overview

| Service | ID | Endpoints | Auth | Version | Base URL |
|---------|-----|-----------|------|---------|----------|
| Authentication Service | `auth-service` | 10 | 6/10 | 1.0.0 | `/api/v1/auth` |
| User Service | `user-service` | 6 | 6/6 | 1.0.0 | `/api/v1/projects` |
| Device Service | `device-service` | 9 | 9/9 | 1.0.0 | `/api/v1` |
| Scan Engine Service | `scan-engine` | 7 | 7/7 | 1.0.0 | `/api/v1` |
| Reporting Service | `reporting-service` | 8 | 8/8 | 1.0.0 | `/api/v1` |
| Notification Service | `notification-service` | 8 | 7/8 | 1.0.0 | `/api/v1` |
| Scheduler Service | `scheduler-service` | 8 | 8/8 | 1.0.0 | `/api/v1` |
| Analytics Service | `analytics-service` | 8 | 8/8 | 1.0.0 | `/api/v1` |
| Billing Service | `billing-service` | 5 | 5/5 | 1.0.0 | `/api/v1` |
| Integration Service | `integration-service` | 8 | 8/8 | 1.0.0 | `/api/v1` |
| Plugin Service | `plugin-service` | 8 | 8/8 | 1.0.0 | `/api/v1` |

---

## Authentication Patterns

### Primary Authentication: X-API-Key Header

All mutating endpoints (POST, PUT, DELETE, PATCH) require the `X-API-Key` header:

```http
POST /api/v1/projects
X-API-Key: dpk_f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2
Content-Type: application/json
```

### Session Authentication: HttpOnly Cookie

Browser-based clients use session-based authentication with HttpOnly cookies:

1. **Login**: `POST /api/v1/auth/login` → Sets `session_id` cookie
2. **Subsequent Requests**: Cookie is sent automatically
3. **Logout**: `POST /api/v1/auth/logout` → Clears cookie (no specific permission required)

### CSRF Protection

All state-changing requests require a CSRF token in the `X-CSRF-Token` header:

1. **Get Token**: `GET /api/v1/auth/csrf-token`
2. **Include in Request**: `X-CSRF-Token: <token>`

### Role-Based Access Control (RBAC)

Three roles with granular permissions (format: `resource:action`):

| Role | Key Permissions | Description |
|------|----------------|-------------|
| `admin` | ALL permissions including `system:config`, `user:manage` | Full access to everything |
| `engineer` | `project:create`, `device:create`, `qomn:execute`, `workflow:manage` | CRUD + calculations, no system config |
| `viewer` | `project:read`, `device:read`, `qomn:read`, `report:read` | Read-only access |

### Permission Reference

| Permission | Description | Admin | Engineer | Viewer |
|-----------|-------------|-------|----------|--------|
| `project:read` | View projects | ✅ | ✅ | ✅ |
| `project:create` | Create projects | ✅ | ✅ | ❌ |
| `project:update` | Update projects | ✅ | ✅ | ❌ |
| `project:delete` | Delete projects | ✅ | ✅ | ❌ |
| `device:read` | View devices | ✅ | ✅ | ✅ |
| `device:create` | Create devices | ✅ | ✅ | ❌ |
| `device:update` | Update devices | ✅ | ✅ | ❌ |
| `device:delete` | Delete devices | ✅ | ✅ | ❌ |
| `connection:read` | View connections | ✅ | ✅ | ✅ |
| `connection:create` | Create connections | ✅ | ✅ | ❌ |
| `element:read` | View UDM elements | ✅ | ✅ | ✅ |
| `element:create` | Create elements | ✅ | ✅ | ❌ |
| `element:delete` | Delete elements | ✅ | ✅ | ❌ |
| `report:read` | View reports | ✅ | ✅ | ✅ |
| `report:generate` | Generate reports | ✅ | ✅ | ❌ |
| `export:read` | Export data | ✅ | ✅ | ✅ |
| `qomn:read` | View QOMN calculations | ✅ | ✅ | ✅ |
| `qomn:execute` | Run QOMN calculations | ✅ | ✅ | ❌ |
| `facp:manage` | Manage FACP panels | ✅ | ✅ | ❌ |
| `facp:read` | View FACP panels | ✅ | ✅ | ✅ |
| `workflow:read` | View workflows | ✅ | ✅ | ✅ |
| `workflow:manage` | Start/approve/reject workflows | ✅ | ✅ | ❌ |
| `integration:read` | View integration status | ✅ | ✅ | ✅ |
| `integration:manage` | Connect to CAD/BIM systems | ✅ | ✅ | ❌ |
| `health:read` | Health check access | ✅ | ✅ | ✅ |
| `monitor:read` | System monitoring access | ✅ | ✅ | ✅ |
| `system:config` | System configuration | ✅ | ❌ | ❌ |
| `user:manage` | User/memory management | ✅ | ❌ | ❌ |
| `conflict:read` | View conflicts | ✅ | ✅ | ✅ |
| `conflict:resolve` | Resolve conflicts | ✅ | ✅ | ❌ |

---

## Standard Error Response Format

All API errors follow a consistent JSON structure:

```json
{
  "success": false,
  "data": null,
  "message": "Human-readable error description"
}
```

### Standard HTTP Status Codes

| Status Code | Meaning | When Used |
|-------------|---------|-----------|
| 200 | OK | Successful GET, PUT, DELETE |
| 201 | Created | Successful POST (resource created) |
| 400 | Bad Request | Invalid input, validation error |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions (e.g., `system:config` required) |
| 404 | Not Found | Resource does not exist |
| 422 | Unprocessable Entity | Valid JSON but semantically invalid (e.g., wrong IFC version) |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected server error |
| 503 | Service Unavailable | Optional dependency not installed (e.g., `pip install fireai[workflow]`) |

---

## Service Dependency Map

```
┌─────────────────────────────────────────────────────────┐
│                    API Gateway (/api/v1)                  │
└───────────────┬─────────────────────┬───────────────────┘
                │                     │
    ┌───────────▼──────┐    ┌────────▼────────┐
    │  auth-service     │    │  user-service     │
    │  (JWT + Sessions) │    │  (Projects CRUD)  │
    └────────┬──────────┘    └────────┬─────────┘
             │                        │
    ┌────────▼────────────────────────▼─────────┐
    │              device-service                │
    │  (Devices, Elements, Connections)          │
    └──┬─────────┬──────────┬───────────────────┘
       │         │          │
  ┌────▼───┐ ┌──▼──────┐ ┌▼──────────────────┐
  │ scan   │ │ report  │ │  notification      │
  │ engine │ │ service │ │  service           │
  └────┬───┘ └──┬──────┘ └──┬────────────────┘
       │        │           │
  ┌────▼────────▼───────────▼──────────────────┐
  │           analytics-service                 │
  │  (QOMN, FACP, Monitor)                     │
  └──┬─────────────────────────────────────────┘
     │
  ┌──▼──────────────────────────────────────────┐
  │           scheduler-service                  │
  │  (Workflow, Memory)                         │
  └──┬──────────────────────────────────────────┘
     │
  ┌──▼──────────────────────────────────────────┐
  │          integration-service                 │
  │  (AutoCAD, Revit, ETAP, CAD, Digital Twin)  │
  └──┬──────────────────────────────────────────┘
     │
  ┌──▼──────────────────────────────────────────┐
  │           plugin-service                     │
  │  (AI Copilot, LLM, GraphRAG, Webhooks)      │
  └─────────────────────────────────────────────┘
```

---

## Versioning Strategy

- **v1 API** (`/api/v1/`): Current stable API. All endpoints documented here.
  - Deprecation headers: `Deprecation: true`, `Sunset: Wed, 25 Jun 2027 00:00:00 GMT`
  - Link header: `Link: </api/v2/...>; rel="successor-version"`
- **v2 API** (`/api/v2/`): Next-generation API with cloud-native features.
  - New features: Generative Design, BIM Provider, IFC 4.3, AR Export, Webhooks
- **Migration Window**: 1 year from V132 release (2026-06-25)

---

## Base URLs

| Environment | Base URL |
|-------------|----------|
| Production | `https://your-domain.com/api/v1` |
| Staging | `https://staging.your-domain.com/api/v1` |
| Development | `http://localhost:8000/api/v1` |

---

## Complete Endpoint List

| Method | Path | Service | Summary | Auth | Permission |
|--------|------|---------|---------|------|------------|
| `POST  ` | `/api/v1/auth/login` | auth-service | Authenticate with API key and receive HttpOnly session cookie | ❌ | — |
| `POST  ` | `/api/v1/auth/session/login` | auth-service | Session-based login (alternate path) | ❌ | — |
| `POST  ` | `/api/v1/auth/logout` | auth-service | Clear session cookie and revoke server-side session | ❌ | — |
| `GET   ` | `/api/v1/auth/me` | auth-service | Get current session role | ✅ | any role |
| `GET   ` | `/api/v1/auth/csrf-token` | auth-service | Get CSRF token for state-changing requests | ❌ | — |
| `GET   ` | `/api/v1/admin/keys` | auth-service | List all API keys with metadata | ✅ | `system:config` |
| `POST  ` | `/api/v1/admin/keys` | auth-service | Create a new API key | ✅ | `system:config` |
| `PUT   ` | `/api/v1/admin/keys/{key_hash}` | auth-service | Update an existing API key role or metadata | ✅ | `system:config` |
| `DELETE` | `/api/v1/admin/keys/{key_hash}` | auth-service | Revoke an API key | ✅ | `system:config` |
| `GET   ` | `/api/v1/admin/keys/roles` | auth-service | Get available API key roles and permissions | ✅ | `system:config` |
| `GET   ` | `/api/v1/projects` | user-service | List all projects with pagination and filtering | ✅ | `project:read` |
| `POST  ` | `/api/v1/projects` | user-service | Create a new fire alarm engineering project | ✅ | `project:create` |
| `GET   ` | `/api/v1/projects/{project_id}` | user-service | Get project details by ID | ✅ | `project:read` |
| `PUT   ` | `/api/v1/projects/{project_id}` | user-service | Update project details | ✅ | `project:update` |
| `DELETE` | `/api/v1/projects/{project_id}` | user-service | Delete a project and all associated data | ✅ | `project:delete` |
| `GET   ` | `/api/v1/projects/{project_id}/export/revit` | user-service | Export project data as Revit file | ✅ | `export:read` |
| `GET   ` | `/api/v1/projects/{project_id}/devices` | device-service | List all devices in a project | ✅ | `device:read` |
| `POST  ` | `/api/v1/projects/{project_id}/devices` | device-service | Create a new fire alarm device | ✅ | `device:create` |
| `GET   ` | `/api/v1/projects/{project_id}/devices/{device_id}` | device-service | Get a specific device by ID | ✅ | `device:read` |
| `PUT   ` | `/api/v1/projects/{project_id}/devices/{device_id}` | device-service | Update a device's properties | ✅ | `device:update` |
| `DELETE` | `/api/v1/projects/{project_id}/devices/{device_id}` | device-service | Delete a device from a project | ✅ | `device:delete` |
| `GET   ` | `/api/v1/elements` | device-service | List building elements with filtering | ✅ | `element:read` |
| `POST  ` | `/api/v1/elements` | device-service | Create a new building element | ✅ | `element:create` |
| `GET   ` | `/api/v1/elements/{element_id}` | device-service | Get a specific building element by ID | ✅ | `element:read` |
| `DELETE` | `/api/v1/elements/{element_id}` | device-service | Soft-delete a building element | ✅ | `element:delete` |
| `POST  ` | `/api/v1/autocad/read_dwg` | scan-engine | Read and parse a DWG file | ✅ | `integration:read` |
| `POST  ` | `/api/v1/autocad/upload_dwg` | scan-engine | Upload and parse a DWG file | ✅ | `integration:read` |
| `POST  ` | `/api/v1/revit/read_rvt` | scan-engine | Read and parse a Revit file | ✅ | `integration:read` |
| `POST  ` | `/api/v1/revit/upload_rvt` | scan-engine | Upload and parse a Revit file | ✅ | `integration:read` |
| `GET   ` | `/api/v1/digital-twin/status` | scan-engine | Get Digital Twin conversion engine status | ✅ | `element:read` |
| `POST  ` | `/api/v1/digital-twin/configure` | scan-engine | Configure Digital Twin conversion settings | ✅ | `system:config` |
| `GET   ` | `/api/v1/digital-twin/mappings` | scan-engine | List all configured format mappings | ✅ | `element:read` |
| `GET   ` | `/api/v1/projects/{project_id}/reports` | reporting-service | List all reports for a project | ✅ | `report:read` |
| `POST  ` | `/api/v1/projects/{project_id}/reports` | reporting-service | Create a new report | ✅ | `report:generate` |
| `POST  ` | `/api/v1/projects/{project_id}/reports/generate` | reporting-service | Generate an engineering report | ✅ | `report:generate` |
| `GET   ` | `/api/v1/projects/{project_id}/reports/{report_id}` | reporting-service | Get a specific report by ID | ✅ | `report:read` |
| `GET   ` | `/api/v1/projects/{project_id}/reports/{report_id}/export` | reporting-service | Export a report as downloadable file | ✅ | `report:read` |
| `POST  ` | `/api/v1/projects/{project_id}/reports/ahj-submittal` | reporting-service | Generate AHJ submittal package | ✅ | `report:generate` |
| `GET   ` | `/api/v1/projects/{project_id}/export/dxf` | reporting-service | Export project data as DXF | ✅ | `export:read` |
| `GET   ` | `/api/v1/projects/{project_id}/export/ifc` | reporting-service | Export project data as IFC | ✅ | `export:read` |
| `GET   ` | `/api/v1/environment/weather` | notification-service | Get weather data for a location | ✅ | `qomn:read` |
| `GET   ` | `/api/v1/environment/geocode` | notification-service | Geocode an address to coordinates | ✅ | `qomn:read` |
| `GET   ` | `/api/v1/environment/hazmat` | notification-service | Check hazardous materials for a location | ✅ | `qomn:read` |
| `GET   ` | `/api/v1/environment/air-quality` | notification-service | Get air quality index for a location | ✅ | `qomn:read` |
| `GET   ` | `/api/v1/environment/severe-weather` | notification-service | Check severe weather alerts for a location | ✅ | `qomn:read` |
| `GET   ` | `/api/v1/environment/full-context` | notification-service | Get complete environmental context for a location | ✅ | `qomn:read` |
| `POST  ` | `/api/v1/projects/{project_id}/sync` | notification-service | Synchronize project data | ✅ | `project:update` |
| `GET   ` | `/api/v1/health` | notification-service | Health check with database connectivity | ✅ | `health:read` |
| `POST  ` | `/api/v1/workflow/start` | scheduler-service | Start a new engineering workflow | ✅ | `workflow:manage` |
| `GET   ` | `/api/v1/workflow/status` | scheduler-service | List all workflow statuses | ✅ | `workflow:read` |
| `GET   ` | `/api/v1/workflow/{workflow_id}/status` | scheduler-service | Get specific workflow status | ✅ | `workflow:read` |
| `POST  ` | `/api/v1/workflow/{workflow_id}/approve` | scheduler-service | Approve a workflow step | ✅ | `workflow:manage` |
| `POST  ` | `/api/v1/workflow/{workflow_id}/reject` | scheduler-service | Reject a workflow step | ✅ | `workflow:manage` |
| `POST  ` | `/api/v1/memory/add` | scheduler-service | Store a new memory for AI agent context | ✅ | `user:manage` |
| `POST  ` | `/api/v1/memory/search` | scheduler-service | Search AI agent memories | ✅ | `qomn:read` |
| `GET   ` | `/api/v1/workflow/{workflow_id}/audit` | scheduler-service | Get workflow audit trail | ✅ | `workflow:read` |
| `GET   ` | `/api/v1/monitor/health` | analytics-service | Get system health metrics | ✅ | `monitor:read` |
| `GET   ` | `/api/v1/monitor/metrics` | analytics-service | Get Prometheus-style metrics | ✅ | `monitor:read` |
| `GET   ` | `/api/v1/monitor/engine-status` | analytics-service | Get QOMN engine status | ✅ | `monitor:read` |
| `POST  ` | `/api/v1/qomn/smoke-spacing` | analytics-service | Calculate NFPA 72 smoke detector spacing | ✅ | `qomn:execute` |
| `POST  ` | `/api/v1/qomn/battery` | analytics-service | Calculate NFPA 72 battery requirements | ✅ | `qomn:execute` |
| `POST  ` | `/api/v1/qomn/voltage-drop` | analytics-service | Calculate voltage drop per NFPA 72 | ✅ | `qomn:execute` |
| `POST  ` | `/api/v1/facp/select` | analytics-service | Select optimal FACP panel for project | ✅ | `facp:manage` |
| `GET   ` | `/api/v1/qomn/audit` | analytics-service | Get QOMN calculation audit trail | ✅ | `qomn:read` |
| `GET   ` | `/api/v1/settings` | billing-service | Get application settings | ✅ | `system:config` |
| `PUT   ` | `/api/v1/settings` | billing-service | Update application settings | ✅ | `system:config` |
| `GET   ` | `/api/v1/settings/keys/openai` | billing-service | Get OpenAI API key configuration | ✅ | `system:config` |
| `PUT   ` | `/api/v1/settings/keys/openai` | billing-service | Update OpenAI API key | ✅ | `system:config` |
| `GET   ` | `/api/v1/health/statistics` | billing-service | Get system usage statistics | ✅ | `health:read` |
| `POST  ` | `/api/v1/autocad/connect` | integration-service | Connect to AutoCAD instance | ✅ | `integration:manage` |
| `POST  ` | `/api/v1/revit/connect` | integration-service | Connect to Revit instance | ✅ | `integration:manage` |
| `GET   ` | `/api/v1/revit/elements` | integration-service | List all Revit elements | ✅ | `integration:read` |
| `POST  ` | `/api/v1/revit/elements/create/wall` | integration-service | Create a wall element in Revit | ✅ | `integration:manage` |
| `POST  ` | `/api/v1/integrations/etap/connect` | integration-service | Connect to ETAP power system analysis | ✅ | `integration:manage` |
| `GET   ` | `/api/v1/integrations/etap/projects` | integration-service | List ETAP projects | ✅ | `integration:read` |
| `POST  ` | `/api/v1/mining/compliance-report` | integration-service | Generate mining compliance report | ✅ | `qomn:execute` |
| `POST  ` | `/api/v1/cad/connect` | integration-service | Connect to generic CAD system | ✅ | `integration:manage` |
| `POST  ` | `/api/v1/engineering-copilot/process-request` | plugin-service | Process AI engineering copilot request | ✅ | `qomn:execute` |
| `POST  ` | `/api/v1/engineering-copilot/validate-model` | plugin-service | Validate an engineering model with AI | ✅ | `qomn:execute` |
| `POST  ` | `/api/v1/llm/chat` | plugin-service | Send a chat message to the LLM service | ✅ | `qomn:execute` |
| `GET   ` | `/api/v1/self-healing/health` | plugin-service | Get self-healing system health | ✅ | `system:config` |
| `POST  ` | `/api/v1/generative/design` | plugin-service | Generate design alternatives using AI | ✅ | `qomn:execute` |
| `POST  ` | `/api/v1/webhooks/subscribe` | plugin-service | Subscribe to webhook events | ✅ | `system:config` |
| `POST  ` | `/api/v1/graphrag/ask` | plugin-service | Ask a question using GraphRAG knowledge base | ✅ | `qomn:execute` |
| `GET   ` | `/api/v1/multi-db/health` | plugin-service | Get multi-database system health | ✅ | `system:config` |

---

## Statistics

| Metric | Value |
|--------|-------|
| Total Endpoints | 85 |
| Total Services | 11 |
| DELETE endpoints | 4 |
| GET endpoints | 39 |
| POST endpoints | 37 |
| PUT endpoints | 5 |
| Auth Required | 81 |
| No Auth Required | 4 |

---

## Pagination Standard

All list endpoints use the same pagination pattern:

**Query Parameters:**
- `page` (integer, 1-indexed, default: 1)
- `limit` (integer, 1-100, default: 20)
- `sort` (string, default: varies)
- `order` (string: "asc" or "desc", default: "desc")

**Response Format:**
```json
{
  "success": true,
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "limit": 20,
    "total_pages": 5
  }
}
```

## Date/Time Standard

All timestamps use ISO 8601 format: `2026-07-30T12:00:00Z`

## ID Standard

All resource IDs are UUIDs: `prj_k1l2m3n4o5p6`, `dev_a1b2c3d4e5f6`

---

*Generated by Datapuff API Specification Generator*  
*Project: Datapuff (BAZspark)*  
*Architect: Eng. Ahmed Elbaz*
