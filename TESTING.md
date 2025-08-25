# Testing Documentation

This document provides comprehensive information about the testing framework for the Changelog Generator project.

## Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Getting Started](#getting-started)
- [Running Tests](#running-tests)
- [Test Categories](#test-categories)
- [Coverage Requirements](#coverage-requirements)
- [Writing New Tests](#writing-new-tests)
- [CI/CD Integration](#cicd-integration)
- [Troubleshooting](#troubleshooting)

## Overview

The Changelog Generator includes a comprehensive test suite designed to ensure reliability, security, and performance. The testing framework covers:

- **Unit Tests**: Test individual functions and methods in isolation
- **Integration Tests**: Test complete workflows and component interactions
- **Security Tests**: Validate input sanitization and security measures
- **Performance Tests**: Ensure the system performs well under load
- **Edge Case Tests**: Handle boundary conditions and error scenarios

### Test Statistics

- **Total Test Files**: 8
- **Target Coverage**: >90%
- **Test Categories**: 5 (Unit, Integration, Security, Performance, Edge Cases)
- **Python Versions Tested**: 3.9, 3.10, 3.11, 3.12

## Test Structure

```
tests/
├── conftest.py                 # Global pytest configuration and fixtures
├── unit/                       # Unit tests
│   ├── test_github_data_fetch.py
│   ├── test_summarisation.py
│   ├── test_security.py
│   ├── test_settings.py
│   └── test_edge_cases.py
├── integration/                # Integration tests
│   └── test_end_to_end_workflow.py
├── performance/                # Performance tests
│   └── test_performance.py
└── security/                   # Security tests
    └── test_security_comprehensive.py
```

## Getting Started

### Prerequisites

- Python 3.9+
- pip package manager
- Git

### Installation

1. **Clone the repository** (if not already done):
```bash
git clone <repository-url>
cd changelog-generator-1
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Verify installation**:
```bash
pytest --version
```

### Configuration

The test suite uses `pytest.ini` for configuration. Key settings include:

- **Coverage target**: 90% minimum
- **Test discovery**: Automatic discovery of `test_*.py` files
- **Markers**: Custom markers for test categorization
- **Report formats**: HTML, XML, and terminal coverage reports

## Running Tests

### Quick Start

Run all tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=. --cov-report=html
```

### Test Categories

#### Unit Tests
Test individual components in isolation:
```bash
pytest tests/unit/ -v
```

#### Integration Tests
Test end-to-end workflows:
```bash
pytest tests/integration/ -v
```

#### Security Tests
Validate security measures:
```bash
pytest tests/security/ -v -m security
```

#### Performance Tests
Test performance and scalability:
```bash
pytest tests/performance/ -v -m performance
```

#### Edge Case Tests
Test boundary conditions:
```bash
pytest tests/unit/test_edge_cases.py -v
```

### Advanced Test Execution

#### Run Specific Test Files
```bash
pytest tests/unit/test_github_data_fetch.py -v
```

#### Run Specific Test Methods
```bash
pytest tests/unit/test_github_data_fetch.py::TestGitHubApiCall::test_successful_api_call -v
```

#### Run Tests by Marker
```bash
pytest -m "unit and not slow" -v
pytest -m "security" -v
pytest -m "performance and slow" -v
```

#### Parallel Execution
```bash
pytest -n auto  # Requires pytest-xdist
```

#### Debug Mode
```bash
pytest --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb
```

### Test Output Options

#### HTML Coverage Report
```bash
pytest --cov=. --cov-report=html
open htmlcov/index.html  # View in browser
```

#### XML Coverage Report
```bash
pytest --cov=. --cov-report=xml
```

#### JSON Test Report
```bash
pytest --json-report --json-report-file=report.json
```

#### HTML Test Report
```bash
pytest --html=report.html --self-contained-html
```

## Test Categories

### Unit Tests (tests/unit/)

**Purpose**: Test individual functions and methods in isolation.

**Coverage Areas**:
- GitHub API interaction functions
- OpenAI integration and prompt handling
- Security validation and sanitization
- Configuration management
- Error handling and edge cases

**Key Features**:
- Comprehensive mocking of external APIs
- Boundary condition testing
- Error scenario validation
- Input/output verification

**Example**:
```python
def test_successful_api_call(self, mock_requests_get, mock_github_token):
    """Test successful GitHub API call."""
    expected_data = {"test": "data"}
    mock_response = MockResponse(expected_data)
    mock_requests_get.return_value = mock_response
    
    response = github_api_call("pulls", "owner", "repo")
    
    assert response == mock_response
```

### Integration Tests (tests/integration/)

**Purpose**: Test complete workflows and component interactions.

**Coverage Areas**:
- End-to-end changelog generation workflow
- API integration patterns
- Data flow between components
- Error propagation and handling
- Configuration integration

**Key Features**:
- Mock external API responses
- Test data pipelines
- Workflow validation
- Cross-component interaction testing

**Example**:
```python
def test_complete_workflow_success(self, mock_github_token, mock_openai_key):
    """Test successful end-to-end changelog generation."""
    # Setup mock responses for GitHub and OpenAI APIs
    # Execute complete workflow
    # Verify changelog generation
```

### Security Tests (tests/security/)

**Purpose**: Validate security measures and input sanitization.

**Coverage Areas**:
- Input validation and sanitization
- XSS prevention
- SQL injection prevention
- Path traversal prevention
- PII removal and data protection
- Authentication security
- Network security measures

**Key Features**:
- Malicious input testing
- Security boundary validation
- Privacy compliance verification
- Authorization testing

**Example**:
```python
def test_xss_prevention(self):
    """Test prevention of XSS attacks."""
    xss_payloads = ['<script>alert("xss")</script>', ...]
    for payload in xss_payloads:
        sanitized = sanitize_commit_message(payload)
        assert '<script>' not in sanitized.lower()
```

### Performance Tests (tests/performance/)

**Purpose**: Ensure the system performs well under various load conditions.

**Coverage Areas**:
- Large dataset processing
- Memory efficiency
- API rate limiting behavior
- Concurrent request handling
- Scalability limits

**Key Features**:
- Benchmark testing
- Memory usage monitoring
- Timeout and performance thresholds
- Load simulation

**Example**:
```python
@pytest.mark.benchmark
def test_message_extraction_benchmark(self, benchmark):
    """Benchmark message extraction performance."""
    result = benchmark(extract_messages_from_commits, large_commit_data)
    assert isinstance(result, str)
```

### Edge Case Tests (tests/unit/test_edge_cases.py)

**Purpose**: Test boundary conditions, error scenarios, and unusual inputs.

**Coverage Areas**:
- Empty and null data handling
- Malformed input processing
- Unicode and encoding edge cases
- Memory and size limits
- Concurrent operation edge cases
- Type conversion edge cases

**Key Features**:
- Boundary value testing
- Error condition simulation
- Resource limit testing
- Data type edge cases

## Coverage Requirements

### Minimum Coverage Thresholds

- **Overall Coverage**: 90% minimum
- **Unit Tests**: 95% minimum for core modules
- **Security Tests**: 100% for security functions
- **Integration Tests**: 80% workflow coverage

### Coverage Exclusions

Files and patterns excluded from coverage:
- Test files (`tests/`)
- Configuration files (`conftest.py`)
- Migration scripts
- Development utilities

### Viewing Coverage

Generate and view HTML coverage report:
```bash
pytest --cov=. --cov-report=html
open htmlcov/index.html
```

Coverage summary in terminal:
```bash
pytest --cov=. --cov-report=term-missing
```

## Writing New Tests

### Test Naming Conventions

- **Test files**: `test_<module_name>.py`
- **Test classes**: `Test<ClassName>` (optional)
- **Test methods**: `test_<functionality>_<scenario>`

### Test Structure (AAA Pattern)

```python
def test_function_scenario(self, fixtures):
    """Test description explaining what is being tested."""
    # Arrange: Set up test data and conditions
    input_data = create_test_data()
    expected_result = "expected_value"
    
    # Act: Execute the function under test
    result = function_under_test(input_data)
    
    # Assert: Verify the results
    assert result == expected_result
    assert other_condition_is_true
```

### Using Fixtures

Common fixtures available:
- `mock_github_token`: Valid GitHub token for testing
- `mock_openai_key`: Valid OpenAI API key for testing
- `sample_pr_data`: Sample PR DataFrame
- `sample_commit_data`: Sample commit DataFrame
- `malicious_input_samples`: Various attack payloads

### Mocking External Dependencies

```python
def test_api_call_with_mock(self, mock_requests_get):
    """Test API call with mocked HTTP response."""
    with patch('module.external_dependency') as mock_dep:
        mock_dep.return_value = expected_value
        
        result = function_that_uses_dependency()
        
        assert result == expected_value
        mock_dep.assert_called_once()
```

### Test Markers

Use markers to categorize tests:
```python
@pytest.mark.unit
def test_unit_functionality():
    """Unit test example."""
    pass

@pytest.mark.integration
@pytest.mark.slow
def test_integration_workflow():
    """Integration test that may be slow."""
    pass

@pytest.mark.security
def test_security_validation():
    """Security test example."""
    pass

@pytest.mark.performance
@pytest.mark.benchmark
def test_performance_benchmark():
    """Performance benchmark test."""
    pass
```

### Parameterized Tests

Test multiple scenarios efficiently:
```python
@pytest.mark.parametrize("input_value,expected", [
    ("valid_input", "expected_output"),
    ("edge_case", "edge_result"),
    ("error_input", None),
])
def test_multiple_scenarios(input_value, expected):
    """Test multiple input scenarios."""
    result = process_input(input_value)
    assert result == expected
```

## CI/CD Integration

### GitHub Actions Workflows

The project includes three main workflows:

#### 1. test.yml - Continuous Testing
- **Triggers**: Push to main/develop, PRs
- **Python versions**: 3.9, 3.10, 3.11, 3.12
- **Test types**: Unit, Integration, Security
- **Additional checks**: Linting, type checking, code quality
- **Reports**: Coverage, test results, security scans

#### 2. deploy.yml - Deployment Pipeline
- **Triggers**: Push to main, version tags
- **Steps**: Test → Security scan → Deploy → Post-deploy tests
- **Environments**: Staging (main branch), Production (tags)
- **Artifacts**: Deployment packages, release notes

#### 3. codeql.yml - Security Analysis
- **Triggers**: Push, PRs, weekly schedule
- **Analysis**: CodeQL security scanning
- **Language**: Python
- **Queries**: Security and quality rules

### Local CI Simulation

Run the same checks locally as CI:

```bash
# Install CI tools
pip install flake8 black isort mypy bandit safety

# Code formatting
black --check .
isort --check-only .

# Linting
flake8 .

# Type checking
mypy . --ignore-missing-imports

# Security scanning
bandit -r .
safety check

# Run all tests
pytest --cov=. --cov-report=html --cov-fail-under=90
```

### Pre-commit Hooks (Optional)

Install pre-commit hooks to run checks automatically:

```bash
pip install pre-commit
pre-commit install
```

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
  
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Import Errors
**Problem**: `ModuleNotFoundError` when running tests
**Solution**:
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
# Or run with pytest from project root
pytest tests/
```

#### 2. Mock Not Working
**Problem**: Mocks not being applied correctly
**Solution**:
- Verify the import path in the patch decorator
- Use `patch.object()` for object methods
- Check that patches are applied in the correct order

#### 3. Fixture Not Found
**Problem**: `pytest.fixture` not available in test
**Solution**:
- Ensure fixture is defined in `conftest.py` or test file
- Check fixture scope (function, class, module, session)
- Verify fixture name spelling

#### 4. Coverage Too Low
**Problem**: Coverage below 90% threshold
**Solution**:
- Identify uncovered lines: `pytest --cov=. --cov-report=term-missing`
- Add tests for missing code paths
- Remove dead code or add `# pragma: no cover` for unreachable code

#### 5. Slow Tests
**Problem**: Tests taking too long to run
**Solution**:
- Use markers to separate slow tests: `pytest -m "not slow"`
- Optimize test data generation
- Use pytest-xdist for parallel execution: `pytest -n auto`

#### 6. Memory Issues
**Problem**: Tests consuming too much memory
**Solution**:
- Use smaller test datasets
- Clean up large objects with `del` and `gc.collect()`
- Monitor memory usage in performance tests

### Debug Test Failures

#### Verbose Output
```bash
pytest -v -s  # Verbose with print statements
```

#### Drop into Debugger
```bash
pytest --pdb  # Drop into pdb on first failure
```

#### Run Specific Failing Test
```bash
pytest tests/unit/test_module.py::test_failing_function -v -s
```

#### Capture and Display Logs
```bash
pytest --log-cli-level=DEBUG
```

### Environment Issues

#### Python Version Compatibility
Ensure you're using a supported Python version:
```bash
python --version  # Should be 3.9+
```

#### Missing Dependencies
Install all required packages:
```bash
pip install -r requirements.txt
pip check  # Verify no dependency conflicts
```

#### Environment Variables
Some tests may require environment variables:
```bash
export PYTHONPATH=/path/to/project
export TESTING=true  # If used by application
```

## Best Practices

### Test Design Principles

1. **Fast**: Unit tests should run quickly
2. **Independent**: Tests should not depend on each other
3. **Repeatable**: Tests should produce consistent results
4. **Self-Validating**: Tests should have clear pass/fail outcomes
5. **Timely**: Write tests early in development

### Test Organization

- Group related tests in classes
- Use descriptive test names
- Keep test files focused on single modules
- Use fixtures for common setup
- Document complex test scenarios

### Maintenance

- Regularly update test dependencies
- Remove obsolete tests when code changes
- Refactor test code to reduce duplication
- Monitor test execution time and optimize slow tests
- Keep test documentation current

### Performance Considerations

- Use appropriate test data sizes
- Mock external dependencies
- Leverage pytest fixtures for expensive setup
- Consider test parallelization for large test suites
- Profile tests to identify bottlenecks

---

For questions or issues with the testing framework, please check the project's issue tracker or consult the development team.