# Multi-stage build for FireAI v1.0
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY ./frontend/package*.json ./frontend/

# Install frontend dependencies
RUN cd ./frontend && npm install --only=production

# Copy backend package files
COPY ./backend/package*.json ./backend/

# Install backend dependencies
RUN cd ./backend && npm install --only=production

# Copy source code
COPY ./frontend ./frontend
COPY ./backend ./backend
COPY ./facp-core ./facp-core

# Build frontend
RUN cd ./frontend && npm run build

# Production stage
FROM node:18-alpine

# Install Python and other system dependencies if needed
RUN apk add --no-cache python3 py3-pip

# Set working directory
WORKDIR /app

# Copy built frontend and backend
COPY --from=builder /app/frontend/build ./frontend/build
COPY --from=builder /app/backend ./backend
COPY --from=builder /app/facp-core ./facp-core

# Copy backend dependencies
COPY --from=builder /app/backend/node_modules ./backend/node_modules

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/facp/health || exit 1

# Start the application
CMD ["node", "./backend/server.js"]