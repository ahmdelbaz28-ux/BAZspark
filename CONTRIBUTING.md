# Contributing to FireAI

Thank you for your interest in contributing to FireAI! This document outlines the process for contributing to our mission-critical fire protection engineering platform.

## 🛡️ Safety-First Development

FireAI is a safety-critical system where errors can have life-threatening consequences. All contributions must follow our rigorous safety protocols:

### Code Requirements
- Every function must include comprehensive safety checks
- All calculations must have error bounds and uncertainty estimates
- Fail-safe behavior is mandatory for all edge cases
- Input validation is required for all external data

### Testing Standards
- 100% branch coverage for safety-critical functions
- Property-based testing for mathematical functions
- Fuzz testing for input parsers
- Regression tests for all bug fixes

## 🚀 Getting Started

### Prerequisites
- Python 3.12+
- Git
- Docker (for integration tests)
- CAD software (optional, for local testing)

### Setup
```bash
# Fork the repository
git clone https://github.com/YOUR_USERNAME/fireai.git
cd fireai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev,test]"
```

## 📝 Development Process

### 1. Find an Issue
- Browse existing [issues](https://github.com/fireai/platform/issues)
- Comment on issues you'd like to work on
- If creating a new issue, follow the template

### 2. Create a Feature Branch
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b bugfix/issue-number-description
```

### 3. Make Changes
- Follow the existing code style
- Add comprehensive tests
- Document your changes
- Ensure all tests pass

### 4. Submit a Pull Request
- Follow the PR template
- Include test results
- Link to related issues
- Wait for code review

## 🧪 Testing Guidelines

### Writing Tests
- Test all edge cases
- Include negative test cases
- Test boundary conditions
- Verify safety properties

### Running Tests
```bash
# Run all tests
make test

# Run specific test suite
pytest tests/unit/

# Run with coverage
pytest --cov=fireai --cov-report=term-missing

# Run integration tests
pytest tests/integration/
```

## 📖 Documentation

### Code Documentation
- All public functions/classes must have docstrings
- Include examples in docstrings
- Document safety considerations
- Update API documentation

### Architecture Documentation
- Update architecture diagrams
- Document design decisions
- Explain safety implications
- Keep README updated

## 🔒 Security Considerations

### Secure Coding Practices
- Validate all inputs
- Escape outputs appropriately
- Follow least privilege principle
- Sanitize sensitive data

### Vulnerability Reporting
- Report security issues immediately
- Use responsible disclosure
- Do not include secrets in code
- Follow security best practices

## 🏗️ Code Style

### Python Style
- Follow PEP 8
- Use type hints everywhere
- Keep functions small (< 50 lines)
- Use descriptive variable names

### Safety-Critical Code
- Use defensive programming
- Include safety assertions
- Handle all error conditions
- Document assumptions clearly

## 🤝 Community Guidelines

### Code of Conduct
- Be respectful to all contributors
- Focus on technical merit
- Assume good intentions
- Help newcomers

### Communication
- Use professional language
- Stay on topic
- Be constructive in feedback
- Acknowledge good work

## 🎯 Issue Labels

- `bug`: Something isn't working
- `enhancement`: New feature or request
- `safety-critical`: Requires extra review attention
- `documentation`: Improvements or additions to documentation
- `good first issue`: Good for newcomers
- `help wanted`: Extra attention is needed

## 🔄 Pull Request Process

1. Update the README.md with details of changes if needed
2. Increase the version number in any examples files and the README.md to the new version that this PR would represent
3. Add yourself to the contributors list
4. Ensure all tests pass
5. Wait for review and address feedback

## 📜 License

By contributing to FireAI, you agree that your contributions will be licensed under the MIT License.

---

**Questions?** Contact the maintainers at [engineering@fireai.org](mailto:engineering@fireai.org)

Thank you for helping make buildings safer!