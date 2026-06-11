# 🔥 FireAI v1.0 - AI Agent Communication Platform

**Production-ready AI engineering platform with distributed agent orchestration**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](VERSION)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](requirements.txt)
[![Node](https://img.shields.io/badge/node->=18.0.0-green.svg)](package.json)

## 🚀 Overview

FireAI v1.0 is a production-ready AI agent communication platform built on the FireAI Agent Communication Protocol (FACP). It enables secure, deterministic, and scalable AI agent orchestration for engineering applications.

### Key Features
- **Secure Communication**: FACP/1.1 protocol with multi-layer validation
- **Distributed Architecture**: L1/L2/L3 three-plane architecture
- **Real-time Dashboard**: Professional UI with execution flow visualization
- **Agent Orchestration**: Planner, Executor, Validator, and Optimizer agents
- **Production Ready**: Docker containers, health checks, and monitoring

## 🏗️ Architecture

```
┌──────────────────────────────┐
│ L1: External Clients (IDE)   │
└─────────────┬────────────────┘
              │ HTTP / WebSocket
              ▼
┌──────────────────────────────┐
│ L2: Orchestrator Cluster     │  (Stateful)
│ - Agent routing              │
│ - Policy engine             │
│ - Task decomposition        │
│ - Load balancing            │
└─────────────┬────────────────┘
              │ Event Bus (Redis/NATS/Kafka abstraction)
              ▼
┌──────────────────────────────┐
│ L3: Engine Worker Cluster    │  (Stateless)
│ - Deterministic execution    │
│ - Power system computation   │
│ - Sandboxed runtime          │
└──────────────────────────────┘
```

## 📋 Prerequisites

- **Python**: 3.12+ (required for FACP core)
- **Node.js**: 18.0+ (required for backend)
- **Docker**: 20.10+ (recommended for deployment)
- **Redis**: 7.0+ (for caching and pub/sub)
- **MongoDB**: 6.0+ (for persistence)

## 🚀 Quick Start

### Option 1: Docker Deployment (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd fireai-v1

# Build and start the services
cd deployment
docker-compose up -d

# Access the application
# Frontend: http://localhost
# Backend API: http://localhost:8000
```

### Option 2: Manual Installation

```bash
# Navigate to the project directory
cd fireai-v1

# Install backend dependencies
cd backend
npm install

# Install frontend dependencies
cd ../frontend
npm install

# Build the frontend
npm run build

# Start the backend server
cd ../backend
npm run dev
```

## 🌐 API Endpoints

### FACP Protocol
- `POST /api/facp/request` - Submit FACP requests
- `GET /api/facp/executions` - Get execution traces
- `GET /api/facp/executions/:id` - Get specific execution
- `GET /api/facp/metrics` - Get system metrics
- `GET /api/facp/health` - Health check
- `GET /api/facp/spec` - Protocol specification

### Agent Management
- `GET /api/agents` - List all agents
- `GET /api/agents/:id` - Get specific agent
- `POST /api/agents/:id/task` - Assign task to agent
- `PUT /api/agents/:id/status` - Update agent status
- `GET /api/agents/:id/capabilities` - Get agent capabilities
- `GET /api/agents/stats` - Get agent statistics

### System Status
- `GET /api/status` - Overall system status
- `GET /api/status/metrics` - Detailed metrics
- `GET /api/status/queue` - Execution queue status
- `GET /api/status/recent-executions` - Recent executions
- `GET /api/status/health` - Health check
- `GET /api/status/config` - System configuration

## 🎨 User Interface

The FireAI v1.0 UI includes:

### Dashboard
- Real-time system metrics
- Agent status overview
- Execution statistics
- Performance indicators

### Chat Interface
- Natural language interaction
- Agent selection panel
- Execution flow visualization
- Request history

### Agent Panel
- Individual agent monitoring
- Capability inspection
- Status management
- Performance metrics

### Execution Status
- Detailed execution traces
- Flow visualization
- Performance analytics
- Error tracking

### Request History
- Query search and filtering
- Performance analysis
- Error logs
- Success/failure rates

## 🔐 Security Features

- **Multi-layer validation**: L1 → L2 → L3 security gates
- **Authentication**: JWT-based user authentication
- **Authorization**: Role-based access control (RBAC)
- **Audit logging**: Comprehensive activity tracking
- **Resource constraints**: Memory, timeout, and recursion limits
- **Idempotency**: Protection against duplicate requests

## 📊 Monitoring & Observability

- **Real-time metrics**: Throughput, latency, error rates
- **Execution tracing**: Complete L1 → L2 → L3 flow tracking
- **Health checks**: Service availability monitoring
- **Performance analytics**: Bottleneck identification
- **Alerting**: Proactive issue detection

## 🛠️ Development

### Environment Setup
```bash
# Copy environment configuration
cp deployment/configs/.env.example .env

# Customize environment variables
# Edit .env with your specific configuration
```

### Running Tests
```bash
# Backend tests
cd backend && npm test

# Frontend tests
cd frontend && npm test
```

### Building for Production
```bash
# Run the build script
./deployment/scripts/build.sh
```

## 🚢 Deployment

### Production Checklist
- [ ] Environment variables configured
- [ ] SSL certificates installed
- [ ] Database connections tested
- [ ] Redis/MongoDB configured
- [ ] Monitoring tools integrated
- [ ] Backup procedures established

### Scaling Guidelines
- **Horizontal scaling**: Add more L3 engine workers
- **Load balancing**: Distribute requests across orchestrators
- **Database sharding**: Scale MongoDB for large datasets
- **CDN integration**: Cache static assets

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For support, please open an issue in the GitHub repository or contact the development team.

---

**FireAI v1.0** - *Transforming Engineering Through AI*

*Built with ❤️ by the FireAI Engineering Team*