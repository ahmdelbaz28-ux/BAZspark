/**
 * FireAI v1.0 Backend Server
 * Main entry point for the FireAI backend services
 */

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const http = require('http');
const socketIo = require('socket.io');
const path = require('path');

// Import routes
const facpRoutes = require('./api/routes/facp');
const agentRoutes = require('./api/routes/agents');
const statusRoutes = require('./api/routes/status');

// Import services
const { FACPService } = require('./services/facp/facpService');
const { AgentService } = require('./services/orchestration/agentService');
const { ExecutionService } = require('./services/engine/executionService');

const app = express();
const server = http.createServer(app);

// Socket.IO setup
const io = socketIo(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  }
});

// Security middleware
app.use(helmet());
app.use(cors({
  origin: process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000', 'http://localhost:3001'],
  credentials: true
}));

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  message: 'Too many requests from this IP, please try again later.'
});
app.use(limiter);

// Body parsing middleware
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Static files
app.use(express.static(path.join(__dirname, '../frontend/build')));

// Initialize services
const facpService = new FACPService();
const agentService = new AgentService();
const executionService = new ExecutionService();

// Inject services into routes
facpRoutes(app, facpService, io);
agentRoutes(app, agentService);
statusRoutes(app, facpService, agentService, executionService);

// Serve React app
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../frontend/build/index.html'));
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({
    error: 'Something went wrong!',
    message: process.env.NODE_ENV === 'development' ? err.message : undefined
  });
});

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({
    error: 'Route not found'
  });
});

const PORT = process.env.PORT || 8000;

server.listen(PORT, () => {
  console.log(`🔥 FireAI v1.0 Backend Server running on port ${PORT}`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
  console.log(`Access the application at: http://localhost:${PORT}`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down gracefully');
  server.close(() => {
    console.log('Process terminated');
  });
});

process.on('SIGINT', () => {
  console.log('SIGINT received, shutting down gracefully');
  server.close(() => {
    console.log('Process terminated');
  });
});

module.exports = { app, server, io };