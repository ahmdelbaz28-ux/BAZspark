#!/bin/bash

# FireAI v1.0 Build Script
# Builds the complete FireAI application for production

set -e  # Exit on any error

echo "🚀 Starting FireAI v1.0 Build Process..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required tools are available
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if ! command -v node &> /dev/null; then
        print_error "Node.js is not installed. Please install Node.js before continuing."
        exit 1
    fi
    
    if ! command -v npm &> /dev/null; then
        print_error "npm is not installed. Please install npm before continuing."
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        print_warn "Docker is not installed. Container builds will not be possible."
    fi
    
    print_status "Prerequisites check passed."
}

# Build frontend
build_frontend() {
    print_status "Building frontend..."
    
    cd frontend
    
    # Install dependencies
    print_status "Installing frontend dependencies..."
    npm install
    
    # Build for production
    print_status "Building frontend for production..."
    npm run build
    
    if [ $? -eq 0 ]; then
        print_status "Frontend build completed successfully."
    else
        print_error "Frontend build failed."
        exit 1
    fi
    
    cd ..
}

# Build backend
build_backend() {
    print_status "Building backend..."
    
    cd backend
    
    # Install dependencies
    print_status "Installing backend dependencies..."
    npm install
    
    # Run tests if available
    if [ -f "package.json" ] && grep -q "test" package.json; then
        print_status "Running backend tests..."
        npm test
    fi
    
    cd ..
}

# Build Docker image
build_docker_image() {
    if command -v docker &> /dev/null; then
        print_status "Building Docker image..."
        
        docker build -t fireai-v1:latest -f deployment/Dockerfile .
        
        if [ $? -eq 0 ]; then
            print_status "Docker image built successfully."
        else
            print_error "Docker build failed."
            exit 1
        fi
    else
        print_warn "Skipping Docker build - Docker not available."
    fi
}

# Run tests
run_tests() {
    print_status "Running comprehensive tests..."
    
    # Frontend tests
    if [ -f "frontend/package.json" ] && grep -q "test" frontend/package.json; then
        cd frontend
        npm test -- --passWithNoTests
        cd ..
    fi
    
    # Backend tests
    if [ -f "backend/package.json" ] && grep -q "test" backend/package.json; then
        cd backend
        npm test
        cd ..
    fi
    
    print_status "Tests completed."
}

# Create production bundle
create_bundle() {
    print_status "Creating production bundle..."
    
    # Create a temporary directory for the bundle
    BUNDLE_DIR="fireai-v1-bundle-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$BUNDLE_DIR"/{frontend,backend,deployment}
    
    # Copy built frontend
    if [ -d "frontend/build" ]; then
        cp -r frontend/build "$BUNDLE_DIR/frontend/"
    fi
    
    # Copy backend files
    cp -r backend "$BUNDLE_DIR/backend/"
    cp -r deployment "$BUNDLE_DIR/deployment/"
    
    # Copy essential files
    cp README.md "$BUNDLE_DIR/" 2>/dev/null || true
    cp LICENSE "$BUNDLE_DIR/" 2>/dev/null || true
    
    print_status "Production bundle created: $BUNDLE_DIR"
    
    # Create tarball
    tar -czf "$BUNDLE_DIR.tar.gz" "$BUNDLE_DIR"
    print_status "Bundle compressed: $BUNDLE_DIR.tar.gz"
    
    # Cleanup
    rm -rf "$BUNDLE_DIR"
}

# Main execution
main() {
    print_status "Starting FireAI v1.0 build process..."
    
    check_prerequisites
    build_frontend
    build_backend
    run_tests
    build_docker_image
    create_bundle
    
    print_status "🎉 FireAI v1.0 build completed successfully!"
    print_status "You can now deploy the application or run it with Docker."
}

# Run main function
main "$@"