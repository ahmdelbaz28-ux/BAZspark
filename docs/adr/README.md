# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) capturing significant technical, structural, and architectural choices made throughout BAZspark development.

## Index of Records

| ADR | Title | Status | Date |
| :--- | :--- | :--- | :--- |
| [0001](0001-device-type-overloading.md) | Device Type Overloading in Fire Protection Schemas | Accepted | 2026-06-12 |
| [0002](0002-test-authentication-isolation-and-warning-suppression.md) | Test Authentication Isolation and Warning Suppression | Accepted | 2026-07-04 |
| [0003](0003-single-source-of-truth-for-nfpa-72-constants.md) | Single Source of Truth for NFPA 72 Constants | Accepted | 2026-07-15 |
| [0004](0004-dual-database-udm-architecture.md) | Dual-Database UDM (Universal Data Model) Architecture | Accepted | 2026-07-20 |
| [0005](0005-self-healing-kernel-fallback-philosophy.md) | Self-Healing Kernel Fallback Philosophy | Accepted | 2026-07-27 |
| [0006](0006-bilingual-voice-control-architecture.md) | Bilingual Voice Control Architecture & State Management | Accepted | 2026-08-17 |

---

## ADR Guidelines

When recording a new decision:
1. Create a sequential file: `docs/adr/000X-title-in-kebab-case.md`.
2. Follow the standard sections: `# Title`, `## Status`, `## Date`, `## Context`, `## Decision`, `## Alternatives Considered`, and `## Consequences`.
3. Update this index table.
