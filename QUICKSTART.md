# FireAI Quick Start Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running Your First Study](#running-your-first-study)
5. [Basic Operations](#basic-operations)
6. [Troubleshooting](#troubleshooting)
7. [Next Steps](#next-steps)

## Prerequisites

Before installing FireAI, ensure your system meets the following requirements:

### System Requirements
- **Operating System**: Windows 10/11, macOS 10.15+, or Linux (Ubuntu 18.04+, CentOS 7+)
- **RAM**: Minimum 8GB (16GB recommended for optimal performance)
- **Storage**: 10GB available disk space
- **Python**: Version 3.8 or higher
- **pip**: Python package installer (usually comes with Python)

### Software Dependencies
- **Git**: Version control system
- **Docker**: Containerization platform (optional, for containerized deployments)
- **ETAP**: Electrical power system analysis software (for electrical studies)
- **GIS Software**: Geographic information system (for mapping studies)

### Recommended Development Environment
- **IDE**: Visual Studio Code, PyCharm, or similar Python IDE
- **Terminal**: Command line interface (PowerShell, Terminal, or Command Prompt)

## Installation

### Method 1: Using pip (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/fireai.git
   cd fireai
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv fireai-env
   source fireai-env/bin/activate  # On Windows: fireai-env\Scripts\activate
   ```

3. **Install FireAI**
   ```bash
   pip install .
   # Or for development installation:
   pip install -e .
   ```

### Method 2: From Source

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/fireai.git
   cd fireai
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install the package**
   ```bash
   pip install -e .
   ```

### Method 3: Docker Installation

1. **Build the Docker image**
   ```bash
   docker build -t fireai .
   ```

2. **Run FireAI container**
   ```bash
   docker run -d -p 8000:8000 fireai
   ```

## Configuration

### Basic Configuration

1. **Create a configuration file**
   Copy the example configuration file and customize it:
   ```bash
   cp config.example.yaml config.yaml
   ```

2. **Edit configuration file**
   Open `config.yaml` and set the following parameters:
   
   ```yaml
   # FireAI Configuration
   app:
     name: "FireAI"
     version: "1.0.0"
     debug: false
     port: 8000
   
   # Security settings
   security:
     jwt_secret: "your-secret-key-here"
     encryption_key: "your-encryption-key"
   
   # ETAP integration (if applicable)
   etap:
     enabled: true
     host: "localhost"
     port: 54321
     username: "your-etap-user"
     password: "your-etap-password"
   
   # Database settings
   database:
     url: "postgresql://user:password@localhost/fireai_db"
   
   # Logging configuration
   logging:
     level: "INFO"
     format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
   ```

3. **Environment Variables** (Alternative method)
   You can also set configuration via environment variables:
   
   ```bash
   export FIREAI_JWT_SECRET="your-secret-key"
   export FIREAI_DATABASE_URL="postgresql://user:password@localhost/fireai_db"
   export FIREAI_DEBUG="true"
   ```

### Security Setup

1. **Generate secure keys**
   ```bash
   # Generate JWT secret
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   
   # Generate encryption key
   python -c "import secrets; print(secrets.token_bytes(32).hex())"
   ```

2. **Set up SSL certificates** (Production)
   ```bash
   openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
   ```

## Running Your First Study

### Using the Command Line Interface

1. **Verify installation**
   ```bash
   fireai --version
   ```

2. **Check system status**
   ```bash
   fireai status
   ```

3. **Create a simple study configuration**
   Create a file named `my_first_study.yaml`:
   
   ```yaml
   study:
     name: "My First FireAI Study"
     description: "A basic example study to demonstrate FireAI capabilities"
     type: "electrical_analysis"
     parameters:
       voltage_level: "medium_voltage"
       equipment_types: ["transformer", "breaker", "cable"]
       analysis_type: "short_circuit"
   
   safety:
     validation_required: true
     risk_threshold: "low"
   
   integration:
     etap_enabled: true
     gis_enabled: false
   ```

4. **Execute the study**
   ```bash
   fireai study create --config my_first_study.yaml
   fireai study execute --id <study_id>
   ```

### Using the Web Interface

1. **Start the web server**
   ```bash
   fireai serve --host 0.0.0.0 --port 8000
   ```

2. **Open your browser** and navigate to `http://localhost:8000`

3. **Sign in** with your credentials (first time users should register)

4. **Create a new study** using the web interface:
   - Click "New Study"
   - Select study type
   - Configure parameters
   - Validate and execute

### Using the API

1. **Start the API server**
   ```bash
   fireai api --port 8000
   ```

2. **Make API requests** (using curl as an example):
   
   ```bash
   # Create a study
   curl -X POST http://localhost:8000/api/studies \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_TOKEN_HERE" \
     -d '{
       "name": "API Study",
       "type": "electrical_analysis",
       "parameters": {
         "voltage_level": "medium_voltage",
         "equipment_types": ["transformer"],
         "analysis_type": "short_circuit"
       }
     }'
   ```

## Basic Operations

### Managing Studies

1. **List all studies**
   ```bash
   fireai study list
   ```

2. **View study details**
   ```bash
   fireai study info --id <study_id>
   ```

3. **Cancel a running study**
   ```bash
   fireai study cancel --id <study_id>
   ```

4. **Delete a study**
   ```bash
   fireai study delete --id <study_id>
   ```

### Configuration Management

1. **View current configuration**
   ```bash
   fireai config show
   ```

2. **Update configuration**
   ```bash
   fireai config set --key security.debug --value true
   ```

### Integration Management

1. **Check ETAP connection**
   ```bash
   fireai integration etap test
   ```

2. **Import ETAP project**
   ```bash
   fireai integration etap import --file path/to/project.etap
   ```

3. **Export study results**
   ```bash
   fireai study export --id <study_id> --format json
   ```

### Security Operations

1. **Check security status**
   ```bash
   fireai security status
   ```

2. **Generate security report**
   ```bash
   fireai security report
   ```

## Troubleshooting

### Common Issues

#### Installation Issues

**Problem**: Package installation fails with dependency errors
**Solution**: 
```bash
# Upgrade pip first
pip install --upgrade pip

# Install with no cache
pip install --no-cache-dir .

# Or install dependencies individually
pip install -r requirements.txt --force-reinstall
```

#### Configuration Issues

**Problem**: Application fails to start due to configuration errors
**Solution**: 
1. Check configuration file syntax (valid YAML/JSON)
2. Ensure all required fields are present
3. Verify that referenced files and services are accessible

#### Connection Issues

**Problem**: Cannot connect to ETAP or other integrated systems
**Solution**:
1. Verify that the integrated system is running
2. Check network connectivity
3. Confirm credentials and permissions
4. Review firewall and security settings

### Diagnostic Commands

1. **System diagnostics**
   ```bash
   fireai diagnose --verbose
   ```

2. **Check system requirements**
   ```bash
   fireai check-system
   ```

3. **View logs**
   ```bash
   fireai logs --follow
   ```

4. **Performance analysis**
   ```bash
   fireai performance analyze
   ```

### Getting Help

1. **View help information**
   ```bash
   fireai --help
   fireai <subcommand> --help
   ```

2. **Check documentation**
   ```bash
   # View online documentation
   fireai docs
   ```

3. **Community support**
   - Check the [GitHub Issues](https://github.com/your-org/fireai/issues) page
   - Join our [Discord community](https://discord.gg/fireai) (if available)
   - Email support: support@fireai.org

## Next Steps

### Learning More

1. **Complete the tutorials**
   - Follow the step-by-step tutorials in the [docs/tutorials](./docs/tutorials/) directory
   - Try different types of studies and configurations

2. **Explore advanced features**
   - Custom integrations
   - Advanced safety protocols
   - Performance optimization techniques

3. **Contribute to the project**
   - Review the [CONTRIBUTING.md](./CONTRIBUTING.md) guide
   - Submit bug reports or feature requests
   - Contribute code improvements

### Production Deployment

When ready for production deployment:

1. **Security hardening**
   - Implement proper authentication and authorization
   - Configure SSL/TLS encryption
   - Set up proper logging and monitoring

2. **Performance optimization**
   - Configure caching appropriately
   - Set up load balancing if needed
   - Optimize database queries

3. **Monitoring and maintenance**
   - Set up comprehensive monitoring
   - Implement backup and disaster recovery procedures
   - Plan for regular updates and maintenance

### Support and Resources

- **Official Documentation**: [https://fireai.readthedocs.io](https://fireai.readthedocs.io)
- **API Reference**: [https://fireai-api-reference.com](https://fireai-api-reference.com)
- **Community Forum**: [https://community.fireai.org](https://community.fireai.org)
- **Commercial Support**: [https://fireai.org/support](https://fireai.org/support)

---

*Congratulations! You've successfully installed and run your first FireAI study. For more detailed information about specific features and capabilities, please refer to the comprehensive documentation in the [docs](./docs/) directory.*