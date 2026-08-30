# Architectural Policy Decision: Unowned Elements & Tenant Boundary Isolation (O2)

**Document ID:** POL-2026-08-30-PHASE1-O2  
**Observation Reference:** Forensic Gate 1A §7.4 Observation O2  
**Authoritative Plan Reference:** `BAZSPARK_PLAN_V2_2.md` §5 Phase 1 (D-1d Policy Decision)  
**Status:** **APPROVED ARCHITECTURAL POLICY (Zero Code Change in Phase 1)**  
**Date:** 2026-08-30  

---

## 1. Problem Statement & Code Traceability

In Forensic Gate 1A (§7.4 Observation O2), the independent auditor identified a potential tenant isolation bypass vector regarding unowned entities:
- **Literal Code Locations:**
  - `backend/database.py` (`Database.get_all_elements`, `Database.create_element`, `Database.update_element`): Historical helper functions allowed element creation with `project_id=None` or `project_id=""`.
  - `backend/routers/elements.py`: When query parameter `project_id` was omitted, the element query layer retrieved elements across projects or elements lacking an assigned project ID.
- **Vulnerability / Architectural Risk:**
  - If elements exist with `project_id=None`, tenant isolation checks that verify project ownership (`author == principal_id` or `principal.role == "admin"`) may be bypassed or behave ambiguously, permitting cross-tenant enumeration or orphan element accumulation.

---

## 2. Options Analysis

| Option | Description | Pros | Cons | Risk Assessment |
|---|---|---|---|---|
| **Option A: Permissive Global Pool** | Allow `project_id=None` as a shared global library/sandbox space. | Backwards compatibility with scratchpads. | Violates multi-tenant isolation; risks data leakage. | **HIGH RISK — REJECTED** |
| **Option B: Implicit Default Project per User** | Auto-assign orphan elements to an implicit `user-default-sandbox` project. | Avoids hard rejection on legacy payloads. | Creates hidden state; complicates billing and revision tracking. | **MEDIUM RISK — REJECTED** |
| **Option C: Strict Fail-Closed Ownership (Mandatory `project_id`)** | Enforce that EVERY element, connection, device, and calculation MUST be bound to a valid, existing `project_id` owned by the authenticated tenant. Unowned entity creation is strictly rejected (HTTP 422/400). | Absolute tenant isolation; airtight OCC revision binding; zero orphan data. | Requires clients to explicitly specify `project_id` on all mutating operations. | **ZERO RISK (SAFETY OPTIMAL) — ACCEPTED** |

---

## 3. Chosen Decision & Rationale

### Decision: **Option C — Strict Fail-Closed Ownership Enforcement**

1. **Mandatory Project Binding:** Every persistent digital twin element (device, circuit, pipe, panel, room, annotation) must possess a valid, non-null `project_id` at creation time.
2. **Strict 404/422 Anti-Enumeration:** Requests attempting to query or mutate elements without a `project_id` or with a non-existent `project_id` will fail closed with anti-enumeration 404 (or 422 validation error).
3. **OCC Revision Invariant:** Project state revision increments can only occur within an identified project boundary. Unowned state mutations are strictly incompatible with OCC concurrency invariants.

---

## 4. Phased Implementation Plan

- **Phase 1 (Current):** Document formal policy decision in `docs/PHASE1_POLICY_DECISIONS.md`. **Zero code changes to database schemas or legacy router filters in Phase 1** (as strictly restricted by D-1d).
- **Phase 2 / Platform Hardening Track:**
  1. Database Schema Migration: Add `NOT NULL` constraint and foreign key on `elements.project_id` referencing `projects.id`.
  2. Data Migration: Run migration script to associate any historical orphan elements with corresponding project IDs or archive them safely.
  3. API Validation: Deprecate optional `project_id` in REST query models; enforce required `project_id` in OpenAPI schemas.

---

## 5. Phase 1 Zero-Code-Change Confirmation

In accordance with Executive Delegation Contract §1-D-1d, this policy decision is formally documented and committed as a specification document. No modifications to `backend/database.py` or database schemas have been made in Phase 1.
