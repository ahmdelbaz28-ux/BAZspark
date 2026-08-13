# API Reference

Base URL: `https://ahmdelbaz28-bazspark.hf.space` (production) or `http://127.0.0.1:8000` (local)

## Authentication

All mutating endpoints require authentication via API key.

### Login (Cookie-based)

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your-api-key"}' \
  -c cookies.txt
```

Subsequent requests use the cookie automatically:

```bash
curl http://localhost:8000/api/v1/auth/me -b cookies.txt
```

### API Key Header (Alternative)

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/projects
```

## Roles

| Role | Permissions |
|---|---|
| `admin` | Full access to all endpoints |
| `engineer` | Create, edit, delete projects/devices/connections; run calculations |
| `reviewer` | Read-only access to all resources; approve/reject |
| `viewer` | Read-only access to projects, devices, reports |
| `api` | Programmatic access with limited scope |

## Endpoints

### Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | System health check |

### Authentication

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Public | Login with API key |
| `POST` | `/api/v1/auth/logout` | Authenticated | Logout |
| `GET` | `/api/v1/auth/me` | Authenticated | Get current user |
| `POST` | `/api/v1/auth/refresh` | `auth:refresh` | Refresh session token |

### Projects

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/projects` | `project:read` | List projects |
| `POST` | `/api/v1/projects` | `project:create` | Create project |
| `GET` | `/api/v1/projects/{id}` | `project:read` | Get project |
| `PUT` | `/api/v1/projects/{id}` | `project:update` | Update project |
| `DELETE` | `/api/v1/projects/{id}` | `project:delete` | Delete project |

### Devices

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/projects/{id}/devices` | `device:read` | List devices |
| `POST` | `/api/v1/projects/{id}/devices` | `device:create` | Add device |
| `PUT` | `/api/v1/devices/{id}` | `device:update` | Update device |
| `DELETE` | `/api/v1/devices/{id}` | `device:delete` | Remove device |

### Connections

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/projects/{id}/connections` | `connection:read` | List connections |
| `POST` | `/api/v1/projects/{id}/connections` | `connection:create` | Create connection |
| `PUT` | `/api/v1/connections/{id}` | `connection:update` | Update connection |
| `DELETE` | `/api/v1/connections/{id}` | `connection:delete` | Delete connection |

### Elements (UDM)

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/elements` | `element:read` | List elements |
| `POST` | `/api/v1/elements` | `element:create` | Create element |
| `PUT` | `/api/v1/elements/{id}` | `element:update` | Update element |
| `DELETE` | `/api/v1/elements/{id}` | `element:delete` | Delete element |

### Conflicts

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/conflicts` | `conflict:read` | List conflicts |
| `POST` | `/api/v1/conflicts/{id}/resolve` | `conflict:resolve` | Resolve conflict |

### QOMN (Fire Alarm Design)

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `POST` | `/api/v1/qomn/smoke-spacing` | `qomn:execute` | Calculate smoke detector spacing |
| `POST` | `/api/v1/qomn/heat-spacing` | `qomn:execute` | Calculate heat detector spacing |
| `POST` | `/api/v1/qomn/coverage` | `qomn:execute` | Analyze room coverage |
| `POST` | `/api/v1/qomn/compliance` | `qomn:execute` | Verify NFPA 72 compliance |

### FDS Simulation

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `POST` | `/api/v1/fds/submit` | `calculation:execute` | Submit FDS simulation job |
| `GET` | `/api/v1/fds/status/{job_id}` | `calculation:read` | Get job status |
| `GET` | `/api/v1/fds/jobs` | `calculation:read` | List all jobs |

### Digital Twin

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `POST` | `/api/v1/digital-twin/convert` | `export:execute` | Convert CAD format |
| `POST` | `/api/v1/digital-twin/upload-and-convert` | `export:execute` | Upload and convert |
| `GET` | `/api/v1/digital-twin/history` | `export:read` | Conversion history |
| `PUT` | `/api/v1/digital-twin/configure` | `system:config` | Configure converter |
| `GET` | `/api/v1/digital-twin/mappings` | `export:read` | Get format mappings |
| `GET` | `/api/v1/digital-twin/status` | `export:read` | Service status |
| `PUT` | `/api/v1/digital-twin/update_mapping` | `system:config` | Update format mapping |
| `GET` | `/api/v1/digital-twin/config` | `export:read` | Get configuration |
| `PUT` | `/api/v1/digital-twin/config` | `system:config` | Update configuration |
| `POST` | `/api/v1/digital-twin/rollback/{version_id}` | `system:config` | Rollback to version |

### Reports

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/reports` | `report:read` | List reports |
| `POST` | `/api/v1/reports/generate` | `report:generate` | Generate report |
| `GET` | `/api/v1/reports/{id}` | `report:read` | Get report |
| `DELETE` | `/api/v1/reports/{id}` | `report:delete` | Delete report |

### Exports

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/exports` | `export:read` | List exports |
| `POST` | `/api/v1/exports/generate` | `export:execute` | Generate export |
| `GET` | `/api/v1/exports/{id}` | `export:read` | Get export |

### Memory (RAG)

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `POST` | `/api/v2/memory/search` | `system:config` | Search memory |
| `GET` | `/api/v2/memory/health` | `health:read` | Memory service health |

### Webhooks & Subscriptions

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `POST` | `/api/v2/webhooks` | `system:config` | Create webhook |
| `GET` | `/api/v2/webhooks` | `system:config` | List webhooks |
| `DELETE` | `/api/v2/webhooks/{id}` | `system:config` | Delete webhook |

### BIM

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v2/bim/providers` | `system:config` | List BIM providers |
| `GET` | `/api/v2/bim/health` | `health:read` | BIM service health |

### GraphRAG

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v2/graphrag/health` | `health:read` | GraphRAG health |

### Topology

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v2/topology/health` | `health:read` | Topology health |

### Workflow

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `POST` | `/api/v1/workflow/execute` | `workflow:manage` | Execute workflow |
| `GET` | `/api/v1/workflow/status/{id}` | `workflow:read` | Get workflow status |
| `GET` | `/api/v1/workflow/list` | `workflow:read` | List workflows |

### Monitoring

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/monitoring/metrics` | `monitor:read` | Prometheus metrics |
| `GET` | `/api/v1/monitoring/health` | `health:read` | Detailed health |

### Marine

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `POST` | `/api/v1/marine/zone-map` | `qomn:execute` | Generate zone mapping |
| `POST` | `/api/v1/marine/fire-resistance` | `qomn:execute` | Calculate fire resistance |
| `POST` | `/api/v1/marine/extinguishment` | `qomn:execute` | Size extinguishing system |

## Error Codes

| Code | Description |
|---|---|
| `FAC-001` | Calculation overflow — input values too large |
| `FAC-002` | Invalid room geometry — self-intersecting or degenerate |
| `FAC-003` | Coverage below minimum threshold (90%) |
| `FAC-004` | Voltage drop exceeds 10% limit |
| `FAC-005` | Battery capacity insufficient for required standby time |

## Rate Limiting

Mutating endpoints are rate-limited via SlowAPI. Exceeding limits returns `429 Too Many Requests`.

## WebSocket

Real-time updates available at `ws://127.0.0.1:8000/ws/{project_id}` for:
- Device placement updates
- Compliance status changes
- Digital Twin conversion progress

## Response Format

All responses follow a consistent format:

```json
{
  "status": "success",
  "data": { ... },
  "meta": {
    "timestamp": "2026-07-25T12:00:00Z",
    "request_id": "req_abc123"
  }
}
```

Error responses:

```json
{
  "status": "error",
  "error": {
    "code": "FAC-003",
    "message": "Coverage below minimum threshold",
    "details": { "coverage": 87.5, "minimum": 90.0 }
  }
}
```
