# Runbook — FireAI Revit MCP Server (stdio)

**Audience:** engineers wiring the FireAI Revit MCP server into MCP clients
(Claude Desktop, Claude Code, VS Code extensions, any JSON-RPC/MCP client).

**Contract status:** A2 (agent-platform-rebuild). `tools/list`, the Gate-1
whitelist, `PARAM_RULES` validation and the routed handlers are now
machine-enforced to be identical (see `tests/test_mcp_server.py::TestA2MCPConformance`).

---

## 1. Transport: stdio ONLY — no docker-compose

The server speaks **MCP over stdio** (JSON-RPC 2.0, one message per line).
It is spawned as a subprocess by the client.

> **Do NOT containerize this server.** Model-write commands are forwarded to
> the C# Revit add-in over a local named pipe (`\\.\pipe\FireAIRevitPipe`).
> Named pipes do not traverse container boundaries, so a containerized server
> can queue updates but never deliver them. Run it on the same host as Revit.

## 2. Client configuration

### claude_desktop_config.json (Claude Desktop)

```json
{
  "mcpServers": {
    "fireai-revit": {
      "command": "C:/path/to/repo/.venv/Scripts/python.exe",
      "args": ["-m", "fireai.mcp_server.revit_mcp_server"],
      "env": {
        "PYTHONPATH": "C:/path/to/repo",
        "FIREAI_ENV": "production"
      }
    }
  }
}
```

### .mcp.json (repo-local clients)

```json
{
  "mcpServers": {
    "fireai-revit": {
      "command": "python",
      "args": ["-m", "fireai.mcp_server.revit_mcp_server"]
    }
  }
}
```

Notes:

* All stderr output is logs; stdout is reserved for protocol frames.
* `FIREAI_MCP_NO_STDIN=1` is **test-only** — never set it for real clients.
* The named-pipe forwarder activates automatically when the Revit add-in is
  running; without it, commands stay queued locally (responses report
  `pipe_status: "no_pipe_client"`).

## 3. Available tools (A2)

| Tool | Type | Purpose |
|---|---|---|
| `place_detector` | write (queued) | NFPA 72 placement plan via `DetectorPlacementEngine`; queues `SET_DETECTOR_LOCATION` actions |
| `calculate_coverage` | read | Coverage radius/spacing/detector count from NFPA 72 Table 17.6.3.1.1 |
| `update_bim_parameter` | write (queued) | Sanitized BIM parameter update via model-update queue + pipe forwarder |
| `update_room_classification` | write (queued) | Hazard classification with mandatory override verification |
| `query_hydraulic_calculation` / `calculate_friction_loss` | read | NFPA 13 Ch. 23 friction loss |
| `validate_sprinkler_compliance` | read | Head pressure vs density compliance |
| `calculate_battery_capacity` | read | NFPA 72 §10.6.7 battery sizing |
| `query_room_hazard_class` | read | Mandatory hazard override table |
| `get_project_status` | read | Live queue stats + session counters |
| `export_report` | read | Session audit log → JSON file (`report_type: "session_audit"`) |

The authoritative machine-readable list is always `tools/list` — its
`inputSchema` objects are generated directly from
`SanitizedMCPHandler.PARAM_RULES`.

## 4. Launch & verification procedure

1. **Smoke-test the process manually** (each line on stdin, responses on stdout):

   ```
   {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"capabilities":{},"clientInfo":{"name":"runbook-check","version":"1.0"}}}
   {"jsonrpc":"2.0","method":"notifications/initialized"}
   {"jsonrpc":"2.0","id":2,"method":"tools/list"}
   {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_project_status","arguments":{}}}
   ```

   Expected: `initialize` returns the SDK protocol revision and server info;
   `tools/list` returns the 11 tools above; the `tools/call` returns
   `"success": true` with queue stats.

2. **Run the conformance suite** before shipping client config changes:

   ```
   pytest tests/test_mcp_server.py -q
   ```

3. **End-to-end check with the add-in** (optional): start Revit with the
   FireAI add-in, call `place_detector` for a small room, then confirm the
   response shows `pipe_status`/queue activity in `get_project_status`.

4. **Audit export:** call `export_report` after a working session and retain
   the JSON file with the submittal records (forensic trail).

## 5. Troubleshooting

| Symptom | Cause | Action |
|---|---|---|
| `Tool '...' is not authorized.` | Tool name not in whitelist | Check spelling against `tools/list`; never bypass Gate 1 |
| `Required parameter '...' is missing` | Args don't match advertised schema | Re-fetch `tools/list`; schemas are generated from PARAM_RULES |
| `pipe_status: "no_pipe_client"` / `"pipe_error"` | Revit add-in not running or pipe busy | Start Revit add-in; command stays queued meanwhile |
| No response to a line | Message was a notification (no `id`) | Notifications get no response per JSON-RPC 2.0 |
| `-32600/-32700` codes | Malformed JSON-RPC framing | One JSON object per line; no NDJSON arrays |
