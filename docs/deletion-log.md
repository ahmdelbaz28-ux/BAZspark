# Mockups Archival Log

## Overview
During Phase 1 (Housekeeping) of the BAZspark Re-engineering, 37 prototype/mockup files from frontend/src/components/mockups/engineering/ were archived.

## Reason for Archival
These files were initially drafted as non-functional UI mockups and prototypes. They caused significant bloat in the main src directory, violating the React 19 architecture's requirement for strict Separation of Privileges and functional components.

However, to prevent the loss of valuable UI/UX layout patterns and lazy-loaded routes from failing, these files were not permanently deleted but were safely moved to archived/mockups-v1/.

## Archived Files
The entire frontend/src/components/mockups/engineering/ directory structure was preserved in archived/mockups-v1/engineering/. This includes:
- AICopilot.tsx
- AdvancedCADWorkspace.tsx
- AuditTrail.tsx
- BMSDashboard.tsx
- ComplianceCenter.tsx
- FireAlarmDesigner.tsx
- Settings.tsx
- dashboard/*
- hooks/*
... and all other related prototype files.

## Next Steps
- When implementing NFPA 72 compliance screens (Phase 4), developers may reference these files for layout inspiration, but must write new, React 19 compliant code in frontend/src/pages/.
- Ensure no dynamic imports (e.g. React.lazy) in App.tsx or Sidebar.tsx still point to the mockups directory.
