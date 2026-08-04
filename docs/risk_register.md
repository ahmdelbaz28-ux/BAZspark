# BAZspark Risk Register

| ID | Category | Risk Description | Probability | Impact | Mitigation Strategy | Owner |
|---|---|---|---|---|---|---|
| R-01 | Technical | SQLite concurrency issues during scale-up (Phase 5). | High | High | Monitor connection pooling and plan migration to PostgreSQL in Q2 2027. Implement strict WAL mode for SQLite. | Backend Team |
| R-02 | Security | Accidental exposure of secrets in new UI settings panels. | Low | Critical | Strict separation of Runtime/Bootstrap/Secrets. CI/CD scanning for hardcoded secrets. No API endpoints return secrets. | DevSecOps |
| R-03 | Compliance | Merkle Tree hashing fails to capture out-of-band DB edits. | Medium | High | Lock down DB access. All modifications must route through the `AuditMerkleTree` append endpoints. | Core Engineering |
| R-04 | Functional | 10 remaining UI rules are not fully implemented. | High | Medium | Add Phase 3b to track the remaining 10 rules. Create a coverage matrix. | Product Manager |
| R-05 | Technical | D3.js visualizer performance drops with >10,000 audit events. | Medium | Low | Implement pagination or lazy loading for the Merkle tree visualizer. | Frontend Team |
| R-06 | Safety | CFD Smoke Simulation re-enabled without deterministic outputs. | Low | Critical | Hardcode `Disabled by V8` constraints in backend. Requires architectural sign-off to lift. | Architect |
| R-07 | Compliance | Zone isolation function fails to reconnect properly. | Low | Critical | Implement mandatory timeout for isolated zones and strict alert thresholds. | Fire Alarm SMEs |
| R-08 | Schedule | Delay in Phase 5 PostgreSQL migration blocking new features. | Medium | Low | Optimize SQLite queries to extend runway until migration is absolutely necessary. | Backend Team |
