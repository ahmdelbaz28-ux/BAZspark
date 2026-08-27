# Claude Desktop Setup & E2E Runbook

This guide covers setting up and verifying the **FireAI Revit MCP Server** inside **Claude Desktop**.

---

## Architecture Overview

The FireAI Revit MCP Server communicates via **JSON-RPC 2.0 over standard I/O (stdio)**:
- Claude Desktop spawns the Python server as a child process.
- All requests (`initialize`, `tools/list`, `tools/call`) flow over `stdin` / `stdout`.
- Logs and telemetry are directed to `stderr` to prevent JSON-RPC frame corruption.
- Write commands are queued safely via `ThreadSafeModelUpdateQueue` for engineer approval.

```
+------------------+         stdio (JSON-RPC 2.0)         +----------------------+
|  Claude Desktop  | <==================================> |   RevitMCPServer     |
+------------------+                                      +----------------------+
                                                                     |
                                                          SanitizedMCPHandler
                                                                     |
                                                          ThreadSafeModelUpdateQueue
                                                                     | (Named Pipe)
                                                          +----------------------+
                                                          |  Revit C# Add-in     |
                                                          +----------------------+
```

---

## Prerequisites

1. **Python 3.10+** environment with repository dependencies installed (`pip install -e .`).
2. **Claude Desktop** installed (macOS or Windows).

---

## Configuration Steps

### 1. Locate Claude Desktop Configuration

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

### 2. Configure `claude_desktop_config.json`

```json
{
  "mcpServers": {
    "fireai-revit": {
      "command": "C:/Users/<USER>/Desktop/BAZ/.venv/Scripts/python.exe",
      "args": [
        "-m",
        "fireai.mcp_server.revit_mcp_server"
      ],
      "cwd": "C:/Users/<USER>/Desktop/BAZ",
      "env": {
        "PYTHONPATH": "C:/Users/<USER>/Desktop/BAZ",
        "FIREAI_ENV": "development"
      }
    }
  }
}
```

### 3. Restart Claude Desktop

Completely quit Claude Desktop from system tray / dock and reopen it.

---

## Available Tools

| Tool | Purpose | Life-Safety Validation |
|------|---------|------------------------|
| `get_project_status` | Returns system health & project metadata | Read-Only query |
| `calculate_coverage` | Calculates NFPA 72 detector spacing & coverage | Deterministic physics formula |
| `place_detector` | Enqueues smoke/heat detector placement in BIM model | Human approval queue gate |
| `get_circuit_load` | Validates NAC/SLC loop voltage and current | NFPA 72 §23.8 calculations |
| `export_report` | Generates NFPA compliance summary report | Read-only report |

---

## Verification & Smoke Testing

Run the automated E2E test suite:
```bash
pytest tests/test_d2_claude_desktop_e2e.py -v
```
