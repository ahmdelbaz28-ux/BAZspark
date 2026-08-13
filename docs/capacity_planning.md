# BAZspark Capacity Planning

## Resources
- **Development Team**: 3 Full-stack Developers, 1 Security Specialist, 1 Fire Alarm SME
- **Duration**: 8 Weeks (for Phases 1-4)
- **Velocity Target**: 25 Story Points / Sprint (2 weeks)

## Milestones

### Sprint 1: Audit Infrastructure
- **Deliverables**: `audit_router.py` deployed, D3.js `AuditVisualizer` component published in Storybook with 100% test coverage.
- **Metrics**: 0 security vulnerabilities in API endpoints, 100% hash chain integrity in test cases.

### Sprint 2: Settings Security Architecture
- **Deliverables**: Refactored `settings_router.py`, `SettingsRegistry` UI deployed.
- **Metrics**: 100% separation of secrets (verified by static analysis and pen-test).

### Sprint 3: NFPA 72 Compliance UI
- **Deliverables**: `ZoneStatusPanel` and `AlarmLogTimeline` completed. `ZoneNavigator` isolation feature deployed.
- **Metrics**: UI accurately reflects 4 mock device states. Isolation triggers Merkle event.

### Sprint 4: Hardening & Remaining 10 Rules Scoping
- **Deliverables**: Risk register reviewed, Phase 3b planned for the remaining 10 rules.
- **Metrics**: Coverage matrix drafted for 14 rules.

## Dependencies & Blockers
- **Blocker**: D3.js learning curve for frontend team (Mitigation: pair programming sessions).
- **Dependency**: NFPA 72 SME required for sign-off on `ZoneNavigator` isolation UX.
