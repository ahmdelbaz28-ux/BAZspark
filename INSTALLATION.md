# FireAI Installation Guide

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Prerequisites](#prerequisites)
3. [Installation Methods](#installation-methods)
4. [Platform-Specific Instructions](#platform-specific-instructions)
5. [Container Installation](#container-installation)
6. [Development Installation](#development-installation)
7. [Verification](#verification)
8. [Post-Installation Configuration](#post-installation-configuration)
9. [Troubleshooting](#troubleshooting)
10. [Uninstallation](#uninstallation)

## System Requirements

### Minimum Requirements
- **Operating System**: Windows 10/11, macOS 10.15+, or Linux (Ubuntu 18.04+, CentOS 7+)
- **CPU**: 2 cores, 2.0 GHz or faster
- **RAM**: 8 GB minimum, 16 GB recommended
- **Storage**: 10 GB available disk space
- **Network**: Internet connection for initial setup and updates

### Recommended Requirements
- **CPU**: 4+ cores, 2.5 GHz or faster
- **RAM**: 16 GB minimum, 32 GB recommended for heavy workloads
- **Storage**: SSD with 20 GB available space
- **Network**: High-speed internet connection

### Software Requirements
- **Python**: 3.8 or higher (3.9+ recommended)
- **pip**: Python package installer (≥21.0)
- **Git**: Version control system (≥2.20)
- **Virtual Environment Tool**: venv, conda, or similar

### Optional Requirements (for full functionality)
- **ETAP**: Electrical power system analysis software
- **GIS Software**: Geographic information system (ArcGIS, QGIS, etc.)
- **Docker**: Containerization platform (≥20.0)
- **PostgreSQL**: Database server (≥12.0) for production use

## Prerequisites

### Python Installation
Ensure Python 3.8+ is installed on your system:

**Windows:**
1. Download Python from [python.org](https://www.python.org/downloads/)
2. During installation, check "Add Python to PATH"

**macOS:**
```bash
# Using Homebrew
brew install python@3.9

# Or using pyenv
brew install pyenv
pyenv install 3.9.16
pyenv global 3.9.16
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

**Linux (CentOS/RHEL):**
```bash
sudo yum install python3 python3-pip
# Or for newer versions:
sudo dnf install python3 python3-pip
```

### Git Installation
**Windows/macOS:** Download from [git-scm.com](https://git-scm.com/)

**Linux:**
```bash
# Ubuntu/Debian
sudo apt install git

# CentOS/RHEL
sudo yum install git
# Or for newer versions:
sudo dnf install git
```

### Verify Prerequisites
```bash
# Check Python version
python --version
# Should show Python 3.8 or higher

# Check pip version
pip --version
# Should show pip version

# Check Git version
git --version
# Should show Git version
```

## Installation Methods

### Method 1: PyPI Installation (Recommended for Users)

This method installs FireAI from the Python Package Index and is recommended for most users.

1. **Create and activate virtual environment** (recommended):
   ```bash
   # Create virtual environment
   python -m venv fireai-env
   
   # Activate virtual environment
   # On Windows:
   fireai-env\Scripts\activate
   # On macOS/Linux:
   source fireai-env/bin/activate
   ```

2. **Upgrade pip** (recommended):
   ```bash
   pip install --upgrade pip
   ```

3. **Install FireAI**:
   ```bash
   pip install fireai
   ```

4. **Verify installation**:
   ```bash
   fireai --version
   ```

### Method 2: GitHub Installation (Latest Development Version)

This method installs the latest development version directly from GitHub.

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-org/fireai.git
   cd fireai
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv fireai-env
   # On Windows:
   fireai-env\Scripts\activate
   # On macOS/Linux:
   source fireai-env/bin/activate
   ```

3. **Install in development mode**:
   ```bash
   pip install -e .
   ```

### Method 3: Local Source Installation

This method installs from a local source code directory.

1. **Navigate to the source directory**:
   ```bash
   cd /path/to/fireai/source
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv fireai-env
   # On Windows:
   fireai-env\Scripts\activate
   # On macOS/Linux:
   source fireai-env/bin/activate
   ```

3. **Install from local source**:
   ```bash
   pip install .
   # Or for development:
   pip install -e .
   ```

## Platform-Specific Instructions

### Windows Installation

1. **Install Python**:
   - Download from [python.org](https://www.python.org/downloads/)
   - During installation, check "Add Python to PATH"
   - Verify installation: `python --version`

2. **Open Command Prompt or PowerShell** as administrator (recommended)

3. **Create virtual environment**:
   ```cmd
   python -m venv fireai-env
   fireai-env\Scripts\activate
   ```

4. **Install FireAI**:
   ```cmd
   pip install --upgrade pip
   pip install fireai
   ```

5. **Verify installation**:
   ```cmd
   fireai --version
   ```

### macOS Installation

1. **Install Python** (if not already installed):
   ```bash
   # Using Homebrew (recommended)
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   brew install python@3.9
   ```

2. **Open Terminal**

3. **Create virtual environment**:
   ```bash
   python3 -m venv fireai-env
   source fireai-env/bin/activate
   ```

4. **Install FireAI**:
   ```bash
   pip install --upgrade pip
   pip install fireai
   ```

5. **Verify installation**:
   ```bash
   fireai --version
   ```

### Linux Installation

#### Ubuntu/Debian

1. **Update package list**:
   ```bash
   sudo apt update
   ```

2. **Install Python and pip**:
   ```bash
   sudo apt install python3 python3-pip python3-venv
   ```

3. **Create virtual environment**:
   ```bash
   python3 -m venv fireai-env
   source fireai-env/bin/activate
   ```

4. **Install FireAI**:
   ```bash
   pip install --upgrade pip
   pip install fireai
   ```

5. **Verify installation**:
   ```bash
   fireai --version
   ```

#### CentOS/RHEL/Fedora

1. **Install Python and pip**:
   ```bash
   # CentOS/RHEL
   sudo yum install python3 python3-pip
   # Or for newer versions:
   sudo dnf install python3 python3-pip
   ```

2. **Create virtual environment**:
   ```bash
   python3 -m venv fireai-env
   source fireai-env/bin/activate
   ```

3. **Install FireAI**:
   ```bash
   pip install --upgrade pip
   pip install fireai
   ```

4. **Verify installation**:
   ```bash
   fireai --version
   ```

## Container Installation

### Docker Installation

1. **Install Docker**:
   - **Windows/macOS**: Download Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop)
   - **Linux**: Follow the official Docker installation guide for your distribution

2. **Verify Docker installation**:
   ```bash
   docker --version
   docker run hello-world
   ```

3. **Pull FireAI Docker image**:
   ```bash
   docker pull your-docker-registry/fireai:latest
   ```

4. **Run FireAI container**:
   ```bash
   docker run -d -p 8000:8000 --name fireai-container your-docker-registry/fireai:latest
   ```

### Building from Dockerfile

1. **Navigate to FireAI source directory**:
   ```bash
   cd /path/to/fireai/source
   ```

2. **Build Docker image**:
   ```bash
   docker build -t fireai:latest .
   ```

3. **Run the container**:
   ```bash
   docker run -d -p 8000:8000 --name fireai-app fireai:latest
   ```

### Docker Compose Installation

1. **Create docker-compose.yml**:
   ```yaml
   version: '3.8'
   
   services:
     fireai:
       build: .
       ports:
         - "8000:8000"
       volumes:
         - ./data:/app/data
         - ./config:/app/config
       environment:
         - PYTHONPATH=/app
         - FIREAI_ENV=production
       restart: unless-stopped
   ```

2. **Run with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

## Development Installation

### Setting Up Development Environment

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-org/fireai.git
   cd fireai
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv fireai-dev
   # On Windows:
   fireai-dev\Scripts\activate
   # On macOS/Linux:
   source fireai-dev/bin/activate
   ```

3. **Install in development mode with extra dependencies**:
   ```bash
   pip install -e ".[dev,test]"
   # Or install everything:
   pip install -r requirements-dev.txt
   ```

4. **Install pre-commit hooks** (if available):
   ```bash
   pre-commit install
   ```

5. **Run tests to verify installation**:
   ```bash
   pytest
   ```

### Installing Specific Versions

1. **Install a specific version**:
   ```bash
   pip install fireai==1.2.3
   ```

2. **Install pre-release version**:
   ```bash
   pip install --pre fireai
   ```

3. **Install from a specific branch/tag**:
   ```bash
   pip install git+https://github.com/your-org/fireai.git@branch-name
   ```

## Verification

### Basic Verification

1. **Check version**:
   ```bash
   fireai --version
   ```

2. **Check help**:
   ```bash
   fireai --help
   ```

3. **Run basic diagnostics**:
   ```bash
   fireai diagnose
   ```

### Functional Verification

1. **Test basic functionality**:
   ```bash
   fireai test-connection
   ```

2. **Check system requirements**:
   ```bash
   fireai check-system
   ```

3. **Verify configuration**:
   ```bash
   fireai config validate
   ```

### Web Interface Verification

1. **Start the web server**:
   ```bash
   fireai serve --port 8000
   ```

2. **Open browser** and navigate to `http://localhost:8000`

3. **Check if the interface loads correctly**

## Post-Installation Configuration

### Initial Configuration

1. **Generate configuration file**:
   ```bash
   fireai init-config
   ```

2. **Edit configuration** in `~/.fireai/config.yaml` or the generated file

3. **Set up security keys**:
   ```bash
   fireai generate-keys
   ```

### Database Setup (if applicable)

1. **Initialize database**:
   ```bash
   fireai db init
   ```

2. **Run migrations**:
   ```bash
   fireai db migrate
   ```

### First-Time Setup

1. **Run first-time setup**:
   ```bash
   fireai setup
   ```

2. **Create admin user** (if applicable):
   ```bash
   fireai user create-admin --username admin --email admin@example.com
   ```

## Troubleshooting

### Common Installation Issues

#### Permission Errors

**Problem**: Permission denied during installation
**Solution**:
```bash
# Use --user flag to install to user directory
pip install --user fireai

# Or create and use virtual environment (recommended)
python -m venv fireai-env
source fireai-env/bin/activate  # On Windows: fireai-env\Scripts\activate
pip install fireai
```

#### Dependency Conflicts

**Problem**: Dependency conflicts during installation
**Solution**:
```bash
# Create fresh virtual environment
python -m venv fresh-env
source fresh-env/bin/activate
pip install --upgrade pip setuptools wheel
pip install fireai
```

#### Missing Dependencies

**Problem**: Missing system dependencies
**Solution** (Linux):
```bash
# Ubuntu/Debian
sudo apt install build-essential libssl-dev libffi-dev python3-dev

# CentOS/RHEL
sudo yum groupinstall "Development Tools"
sudo yum install openssl-devel libffi-devel python3-devel
```

#### Python Version Issues

**Problem**: Incorrect Python version
**Solution**:
```bash
# Check Python version
python --version

# Use specific Python version
python3.9 -m pip install fireai

# Or use pyenv to manage Python versions
pyenv install 3.9.16
pyenv local 3.9.16
pip install fireai
```

### Diagnostic Commands

1. **Check system compatibility**:
   ```bash
   fireai check-system
   ```

2. **Detailed installation diagnostics**:
   ```bash
   fireai diagnose --verbose
   ```

3. **Check environment**:
   ```bash
   pip list | grep fireai
   which fireai
   ```

### Reinstallation

If you need to reinstall FireAI:

1. **Uninstall current version**:
   ```bash
   pip uninstall fireai
   ```

2. **Clean up virtual environment** (if using):
   ```bash
   # Remove virtual environment directory
   rm -rf fireai-env  # On Windows: rmdir /s fireai-env
   ```

3. **Follow installation steps again**

## Uninstallation

### Standard Uninstallation

1. **Uninstall FireAI**:
   ```bash
   pip uninstall fireai
   ```

2. **Confirm removal** when prompted

### Complete Cleanup

1. **Uninstall FireAI and dependencies**:
   ```bash
   pip uninstall fireai
   ```

2. **Remove virtual environment** (if used):
   ```bash
   rm -rf fireai-env  # On Windows: rmdir /s fireai-env
   ```

3. **Remove configuration files** (optional):
   ```bash
   # Remove user configuration
   rm -rf ~/.fireai
   # Remove any config files in current directory
   rm -f config.yaml
   ```

### Docker Cleanup

1. **Stop and remove container**:
   ```bash
   docker stop fireai-container
   docker rm fireai-container
   ```

2. **Remove Docker image**:
   ```bash
   docker rmi your-docker-registry/fireai:latest
   ```

---

*Congratulations! You have successfully installed FireAI. For next steps, please refer to the [QUICKSTART.md](./QUICKSTART.md) guide to begin using the platform.*