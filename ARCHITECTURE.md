# FireAI Architecture

## Overview

FireAI is built as a safety-critical platform for fire protection engineering with emphasis on reliability, accuracy, and compliance. The architecture follows a layered approach with strict separation of concerns and multiple safety gates.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Presentation Layer                           │
├─────────────────────────────────────────────────────────────────┤
│  CAD Integration    │  Web Interface   │  API Gateway          │
│  • AutoCAD Plugin  │  • React UI      │  • RESTful API        │
│  • Revit Add-in    │  • Dashboard     │  • GraphQL API        │
│  • IFC Reader      │  • Reports       │  • WebSocket          │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    Service Layer                                │
├─────────────────────────────────────────────────────────────────┤
│  Engineering Services        │  Integration Services           │
│  • Detector Placement       │  • CAD Parsing                  │
│  • Compliance Checking      │  • BIM Sync                     │
│  • NAC Design              │  • Cloud Storage                │
│  • Evacuation Modeling     │  • Third-party APIs             │
│  • Risk Assessment         │  • Audit Trail                  │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    Core Engine Layer                            │
├─────────────────────────────────────────────────────────────────┤
│  Computational Engine      │  Safety & Validation              │
│  • Spatial Algorithms      │  • Input Validation              │
│  • Optimization Solver     │  • Compliance Verification       │
│  • Physics Simulation      │  • Safety Gates                  │
│  • Coverage Analysis       │  • Error Recovery                │
│  • Load Calculations       │  • Audit Logging                 │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    Data Layer                                   │
├─────────────────────────────────────────────────────────────────┤
│  • Building Models         │  • Engineering Data              │
│  • CAD Geometry            │  • Compliance Rules              │
│  • Sensor Networks         │  • Historical Records            │
│  • System Configurations   │  • Audit Logs                    │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. FireAI Core Engine

The central computational component that performs all engineering calculations:

- **Spatial Analysis Engine**: Uses Shapely/GEOS for geometric calculations
- **Optimization Solver**: Places detectors optimally per NFPA 72
- **Compliance Checker**: Validates against all applicable codes
- **Risk Assessment Module**: Evaluates safety factors and redundancy

### 2. FireAI Agent Communication Protocol (FACP)

A three-layer communication protocol:

```
┌─────────────────┐
│   L1 Interface  │ ← External Boundary (IDEs, Editors, Tools)
│   (Validation)  │
└─────────────────┘
        │
┌─────────────────┐
│   L2 Orchestrator│ ← Policy Enforcement & Task Routing
│   (Controlled)   │
└─────────────────┘
        │
┌─────────────────┐
│   L3 Engine     │ ← Deterministic Execution Kernel
│   (Secure)      │
└─────────────────┘
```

**L1 (Interface)**: Validates all external requests, implements security firewall
**L2 (Orchestrator)**: Routes tasks, enforces policies, manages agents
**L3 (Engine)**: Executes deterministic calculations, performs engineering analysis

### 3. Compliance Engine

Multi-layered code compliance checking:

- **NFPA 72**: National Fire Alarm and Signaling Code
- **NFPA 13**: Sprinkler system requirements
- **IBC**: International Building Code
- **Local Amendments**: Jurisdiction-specific requirements

### 4. CAD Integration Layer

Supports multiple CAD formats:

- **DXF/DWG**: AutoCAD compatibility
- **IFC**: Industry Foundation Classes (BIM)
- **RVT**: Revit native format
- **PDF**: 2D drawing support

## Safety Architecture

### Safety Gates
1. **Input Validation Gate**: Validates all incoming data
2. **Geometry Validation Gate**: Checks CAD geometry validity
3. **Engineering Calculation Gate**: Performs safety-critical calculations
4. **Compliance Verification Gate**: Checks against all applicable codes
5. **Output Validation Gate**: Ensures safe and accurate output

### Fail-Safe Mechanisms
- Conservative assumptions when data is ambiguous
- Multiple independent calculation methods
- Redundant safety checks
- Automatic audit trail generation

### Error Handling
- Graceful degradation on partial failures
- Detailed error reporting
- Recovery mechanisms
- State preservation

## Data Flow

```
CAD File → Parser → Validator → Spatial Engine → Compliance Engine → Output
    ↓           ↓          ↓            ↓               ↓            ↓
Geometry   Validated   Safe Geom   Calcs & Opt.   Code Compliance  Report
```

## Security Architecture

### Defense in Depth
1. **Network Layer**: API gateway with rate limiting
2. **Application Layer**: Input validation and sanitization
3. **Data Layer**: Encrypted storage and access controls
4. **Compute Layer**: Isolated execution environments

### Authentication & Authorization
- Role-based access control (RBAC)
- Multi-factor authentication
- Session management
- API key management

## Deployment Architecture

### Development Environment
- Local installation with full engine
- Mock services for external dependencies
- Development database
- Testing infrastructure

### Production Environment
- Containerized deployment (Docker/Kubernetes)
- Load balancing and scaling
- Monitoring and alerting
- Backup and disaster recovery

## Technology Stack

### Backend
- **Language**: Python 3.12+
- **Framework**: FastAPI
- **Database**: PostgreSQL/SQLite
- **Spatial**: Shapely, GEOS
- **Optimization**: Custom solvers

### Frontend
- **Framework**: React/TypeScript
- **Visualization**: D3.js, Three.js
- **CAD Viewer**: Custom WebGL renderer

### Infrastructure
- **Containerization**: Docker
- **Orchestration**: Kubernetes
- **Monitoring**: Prometheus, Grafana
- **Logging**: ELK Stack

## Performance Characteristics

### Scalability
- Horizontal scaling of computation nodes
- Asynchronous job processing
- Caching layer for common operations
- CDN for static assets

### Reliability
- 99.9% uptime SLA
- Multi-region deployment
- Automated failover
- Comprehensive monitoring

## Safety Considerations

### Engineering Accuracy
- All calculations include uncertainty estimates
- Multiple verification methods
- Conservative safety factors
- Professional engineer review requirements

### System Safety
- No single point of failure
- Comprehensive backup systems
- Regular safety audits
- Continuous monitoring

This architecture ensures FireAI maintains the highest standards of safety, accuracy, and reliability required for fire protection engineering applications.