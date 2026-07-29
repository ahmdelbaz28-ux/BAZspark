# Contributing to BAZSpark

Thank you for contributing to BAZSpark. This is a **safety-critical system** for fire protection engineering. All contributions must meet high standards for correctness, testing, and documentation.

## Safety-First Principles

- All changes must preserve the safety-critical nature of the system
- Modifications to calculation engines require additional review
- Compliance verification components need thorough testing
- Documentation updates must maintain safety warnings
- Fail-safe behavior is mandatory for all edge cases

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 22+
- Git

### Setup

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/BAZspark.git
cd BAZspark

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev,parsing]"

# Run tests
pytest
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b bugfix/issue-number-description
```

### 2. Make Changes

- Follow existing code style
- Add comprehensive tests
- Document your changes
- Ensure all tests pass

### 3. Run Checks

```bash
# Lint
ruff check .

# Type check
mypy fireai/

# Tests
pytest --cov=fireai

# Frontend
cd frontend && npm test
```

### 4. Submit a Pull Request

- Follow the PR template
- Include test results
- Link to related issues
- Wait for code review

## Code Standards

### Python

- **Formatter:** Black
- **Linter:** Ruff
- **Type checker:** MyPy
- **Style:** PEP 8, 4-space indentation

```python
# Good
def calculate_coverage(room: Room) -> float:
    """Calculate NFPA 72 coverage percentage for a room."""
    if room.ceiling_height > MAX_CEILING_HEIGHT:
        raise ValueError(f"Ceiling height {room.ceiling_height}m exceeds maximum")
    return _compute_coverage(room)
```

### TypeScript

- **Formatter:** Biome
- **Linter:** ESLint
- **Style:** 2-space indentation

```typescript
// Good
interface Room {
  width: number;
  length: number;
  ceilingHeight: number;
}

function calculateCoverage(room: Room): number {
  if (room.ceilingHeight > MAX_CEILING_HEIGHT) {
    throw new Error(`Ceiling height ${room.ceilingHeight}m exceeds maximum`);
  }
  return computeCoverage(room);
}
```

## Testing Requirements

### Coverage

- **Safety-critical functions:** 100% branch coverage
- **Core engine:** 90%+ coverage
- **API endpoints:** 85%+ coverage
- **Frontend components:** 80%+ coverage

### Test Types

| Type | Purpose | Required |
|---|---|---|
| Unit | Individual function testing | Always |
| Integration | Component interaction | For new features |
| Property-based | Mathematical correctness | For calculations |
| Fuzz | Input validation | For parsers |
| Regression | Bug fix verification | When fixing bugs |

### Writing Tests

```python
# Good test
def test_smoke_detector_spacing():
    """NFPA 72 §17.7.3.2.3: Smoke detectors max 9.1m on smooth ceilings."""
    room = Room(width=10, length=15, ceiling_height=3.0)
    spacing = calculate_smoke_spacing(room)
    assert spacing <= 9.1  # Never exceed code maximum
    assert spacing > 0     # Always positive

# Property-based test
from hypothesis import given, strategies as st

@given(st.floats(min_value=0.1, max_value=100))
def test_coverage_always_between_0_and_100(width):
    room = Room(width=width, length=10, ceiling_height=3.0)
    coverage = calculate_coverage(room)
    assert 0 <= coverage <= 100
```

## Safety-Critical Changes

Changes to these components require additional review:

- `fireai/core/qomn_kernel.py` — Deterministic calculation kernel
- `fireai/core/nfpa72_engine.py` — NFPA 72 compliance engine
- `fireai/constants/nfpa72.py` — NFPA 72 constants
- `fireai/constants/nec.py` — NEC constants
- `fireai/core/audit_trail.py` — Audit trail

### Requirements

1. **Code review by project lead** (Eng. Ahmed Elbaz)
2. **100% branch coverage** for modified functions
3. **Property-based tests** for mathematical functions
4. **Documentation update** if formulas change
5. **ENGINEERING_BASIS.md update** if constants change

## Pull Request Guidelines

### Title

Use conventional commits:

```
feat: add seismic detection module
fix: correct voltage drop calculation for 10AWG wire
docs: update API reference for marine endpoints
test: add property-based tests for coverage calculator
```

### Description

```markdown
## What

Brief description of changes.

## Why

Link to issue or explain the problem.

## How

Technical approach taken.

## Testing

- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing performed (if applicable)

## Safety Impact

- [ ] No safety impact
- [ ] Safety impact (explain)
```

## Reporting Issues

### Security Vulnerabilities

Report privately to: security@bazspark.com

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact on safety
- Suggested fix (if any)

### Bugs

Open a GitHub issue with:
- Steps to reproduce
- Expected vs actual behavior
- Error messages/logs
- Environment details

## Code of Conduct

- Be respectful and constructive
- Focus on the code, not the person
- Accept feedback gracefully
- Prioritize safety above all else

## Questions?

Open a discussion on GitHub or contact the project lead.
