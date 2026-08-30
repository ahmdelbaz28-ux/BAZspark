# Architectural Decision Record: Deployment Scaling Containment (A6)
**Document ID:** ADR-2026-08-30-A6  
**Status:** ACCEPTED & IMPLEMENTED  
**Scope:** Deployment topologies (Docker Compose, Kubernetes, Helm, Render)  
**Author:** Antigravity / FireAI Engineering Team  
**Baseline:** `610ed62` (Track A / Batch 2)

---

## 1. Single-Instance State Inventory

An architectural audit of the active codebase revealed that several core execution subsystems maintain ephemeral, in-memory state within a single Python process:

1. **`_ws_tickets` Registry (`backend/routers/agent_ws.py`):**
   - Single-use WebSocket connection tickets issued via `POST /agent/ws-ticket` are stored in an in-memory dictionary `_ws_tickets: Dict[str, dict]`.
   - Handshake validation uses `_ws_tickets.pop(ticket, None)`.
2. **`active_agents` & `agent_response_futures` (`backend/routers/agent_ws.py`):**
   - Active WebSocket connections and asynchronous response futures are mapped in memory.
3. **Agent Run Orchestrator & State Store (`backend/services/agent_run_orchestrator.py`):**
   - Active runs, execution loops, pause/resume event signals, and step status queues reside in process memory.
4. **LangGraph Checkpointer / Local State:**
   - In-memory execution checkpointing and local graph state machines that are not yet bound to a shared external store.
5. **OCC Revision Locks:**
   - In-memory project locks and sequence synchronization in SQLite/local state.

---

## 2. Why Multi-Replica Deployment is Unsafe Today

Deploying multiple API replicas behind a standard round-robin or least-connections load balancer without state externalization causes immediate, critical failure modes:

- **Split-Brain WebSocket Handshakes:**
  A client requests a single-use ticket from Replica A, but its subsequent WebSocket upgrade request is routed to Replica B. Replica B has no knowledge of the ticket in Replica A's memory, causing an immediate `4401 UNAUTHORIZED` rejection.
- **Divergent OCC Revisions:**
  Concurrent updates routed to different replicas bypass process-level synchronizations, resulting in silent data corruption or invalid OCC conflicts.
- **Fragmented Run Control:**
  A pause, resume, or cancellation request sent via REST to Replica B cannot signal the execution loop running on Replica A, leaving orphaned background tasks.

---

## 3. Containment Action Executed

To guarantee total protocol safety, zero connection drops, and absolute data integrity, all deployment targets have been explicitly pinned to a single active replica (`replicas: 1`):

- `deploy/docker/docker-compose.yml`: API service pinned to `replicas: 1`.
- `deploy/k8s/deployment-api.yaml`: Deployment `spec.replicas` pinned to `1`.
- `deploy/helm/fireai/values.yaml`: `replicas.api: 1`, `autoscaling.api.enabled: false`, `minReplicas: 1`, `maxReplicas: 1`.
- `render.yaml`: Annotated for single-instance web service execution.

---

## 4. Restoration Path

Restoring multi-replica horizontal scalability will be executed as a dedicated epic during the **Platform Hardening Track** prior to Phase 4:

1. **Distributed Ticket & Session Store:**
   - Migrate `_ws_tickets` from in-memory dictionary to Redis with atomic `GETDEL` (Redis 6.2+) or Lua pop scripts with TTL expiry.
2. **Distributed Pub/Sub Command Bus:**
   - Connect `agent_response_futures` and orchestrator event broadcasting through Redis Pub/Sub or Redis Streams so any replica can dispatch or listen to run events.
3. **Externalized Checkpointer:**
   - Adopt Redis / PostgreSQL-backed LangGraph checkpointer for durable multi-node recovery.
4. **Database-Level Atomic OCC:**
   - Enforce optimistic concurrency control strictly at the ACID database layer (PostgreSQL transactional row versions).

---

## 5. Restoration Measurement Criteria

Multi-replica configurations will only be re-enabled when the following automated verification suite passes:

1. **Distributed Ticket Validation:** 1,000 WebSocket connections negotiated across 5 replicas with zero 4401 ticket-miss errors.
2. **Cross-Replica Run Control:** Pause, resume, and cancel commands issued across distinct replica nodes successfully alter active runs.
3. **Concurrent OCC Collision Integrity:** 100 concurrent agents attempting updates at revision $N$ ensure exactly one succeeds ($N+1$) and 99 fail with deterministic `REVISION_CONFLICT`.
