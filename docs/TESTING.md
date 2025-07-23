# PiFrame Testing Guide

[![Tests](https://github.com/YOUR_USERNAME/piframe/actions/workflows/tests.yml/badge.svg)](https://github.com/YOUR_USERNAME/piframe/actions/workflows/tests.yml)
[![Coverage](https://github.com/YOUR_USERNAME/piframe/actions/workflows/coverage.yml/badge.svg)](https://github.com/YOUR_USERNAME/piframe/actions/workflows/coverage.yml)
[![Health Check](https://github.com/YOUR_USERNAME/piframe/actions/workflows/health-check.yml/badge.svg)](https://github.com/YOUR_USERNAME/piframe/actions/workflows/health-check.yml)

*Note: Replace `YOUR_USERNAME` with your actual GitHub username*

## Overview

PiFrame has a comprehensive test suite covering both the legacy monolithic code and the new modular architecture. The testing infrastructure includes unit tests, integration tests, performance tests, and automated CI/CD pipelines.

## Test Structure

### New Modular Architecture Tests (Primary Focus)

```
tests/
├── test_cache_manager.py      # Cache system (TTL, LRU, thread safety) - 36 tests
├── test_weather_service.py    # Weather API integration - 23 tests
├── test_drive_service.py      # Google Drive operations - 25 tests
└── test_image_service.py      # Image serving & metadata - 24 tests
```

### Legacy Tests (Maintained for Compatibility)

```
tests/
├── test_app.py               # Flask routes and integration
├── test_config.py            # Configuration management
├── test_drive_pictures.py    # Legacy Drive integration
├── test_image_metadata.py    # EXIF data extraction
├── test_integration.py       # End-to-end workflows
└── test_performance.py       # System performance monitoring
```

## Running Tests Locally

### Quick Start (New Architecture Only)

```bash
# Run all new modular architecture tests
python -m unittest discover tests -p "test_*_service.py" -v
python -m unittest tests.test_cache_manager -v

# Run specific service tests
python -m unittest tests.test_weather_service -v
python -m unittest tests.test_cache_manager -v
```

### Comprehensive Testing

```bash
# Run all tests with coverage
python run_tests.py

# Run specific test categories
python run_tests.py --unit-only
python run_tests.py --integration-only
python run_tests.py --performance-only

# Run without coverage (faster)
python run_tests.py --no-coverage

# Skip Google Drive integration tests (for CI-like testing)
python run_tests.py --skip-drive
```

### Test Individual Components

```bash
# Test cache system
python -m unittest tests.test_cache_manager.TestTTLCache -v

# Test weather service
python -m unittest tests.test_weather_service.TestWeatherService -v

# Test drive service  
python -m unittest tests.test_drive_service.TestDriveService -v

# Test image service
python -m unittest tests.test_image_service.TestImageService -v
```

## CI/CD Pipeline

### Workflow Types

1. **PR Tests (Fast)** - `pr-tests.yml`
   - Runs on pull requests
   - Quick validation tests (~30 seconds)
   - Core functionality verification
   - Legacy compatibility check

2. **Full Tests** - `tests.yml`
   - Runs on main branch pushes
   - Complete test matrix (Python 3.9-3.12)
   - All test categories
   - Code quality checks

3. **Coverage Report** - `coverage.yml`
   - Weekly coverage analysis
   - Codecov integration
   - Performance benchmarking
   - Artifact generation

4. **Health Check** - `health-check.yml`
   - Daily dependency scanning
   - Security vulnerability checks
   - Cross-platform compatibility
   - Performance regression detection

### Python Version Support

The test suite runs on:
- ✅ Python 3.9 (Minimum supported)
- ✅ Python 3.10
- ✅ Python 3.11 (Primary development)
- ✅ Python 3.12 (Latest)

### Platform Support

Tests run on:
- ✅ Ubuntu Latest (Primary)
- ✅ Windows Latest
- ✅ macOS Latest

## Test Coverage

### Current Coverage (New Architecture)

| Component | Coverage | Lines | Description |
|-----------|----------|-------|-------------|
| Cache Manager | 100% | 154/154 | TTL cache, LRU eviction, thread safety |
| Configuration | 38% | 38/99 | Settings management, env vars |
| Logging | 19% | 12/64 | Structured logging, performance decorators |
| Services | 0%* | 0/519 | Weather, Drive, Image services |

*Services show 0% in isolated runs but are extensively tested via unit tests

### Coverage Goals

- **Target**: 85% overall coverage
- **Critical Components**: 100% (cache, core services)
- **Configuration**: 80%+
- **Legacy Code**: Maintained compatibility

## Writing New Tests

### Test Structure

```python
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from piframe.services.your_service import YourService
from piframe.config.settings import Config

class TestYourService(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.service = YourService(self.config)
    
    def test_basic_functionality(self):
        result = self.service.some_method()
        self.assertIsNotNone(result)
```

### Testing Guidelines

1. **Mock External Dependencies**: Always mock API calls, file operations, network requests
2. **Test Error Conditions**: Include error handling and edge cases
3. **Use Descriptive Names**: Test names should describe what is being tested
4. **Test Both Success and Failure**: Cover happy path and error scenarios
5. **Thread Safety**: Test concurrent operations where applicable

### Mocking Examples

```python
# Mock HTTP requests
@patch('requests.Session')
def test_api_call(self, mock_session_class):
    mock_response = MagicMock()
    mock_response.json.return_value = {'data': 'test'}
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mock_session_class.return_value = mock_session

# Mock file operations
@patch('builtins.open', new_callable=mock_open, read_data='test data')
def test_file_read(self, mock_file):
    # Test code here

# Mock cache manager
mock_cache_manager = MagicMock()
mock_cache_manager.get.return_value = None
```

## Performance Testing

### Cache Performance

```python
# Test cache operations per second
def test_cache_performance(self):
    cache = TTLCache(max_size=1000, default_ttl=60)
    
    start_time = time.time()
    for i in range(1000):
        cache.set(f'key_{i}', f'value_{i}')
        cache.get(f'key_{i}')
    end_time = time.time()
    
    ops_per_second = 2000 / (end_time - start_time)
    self.assertGreater(ops_per_second, 10000)  # Should be > 10k ops/sec
```

### Memory Usage

```python
# Monitor memory usage during operations
def test_memory_usage(self):
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss
    
    # Perform operations
    cache = TTLCache(max_size=1000, default_ttl=60)
    for i in range(1000):
        cache.set(f'key_{i}', f'value_{i}' * 100)
    
    final_memory = process.memory_info().rss
    memory_increase = final_memory - initial_memory
    self.assertLess(memory_increase, 50 * 1024 * 1024)  # < 50MB increase
```

## Google Drive Integration Testing

### CI vs Local Testing

**CI Environment (GitHub Actions)**:
- Google Drive integration tests are automatically skipped
- Uses `CI=true` environment variable detection
- Tests run with mocked Google Drive API responses only
- No real Google Drive credentials required

**Local Development**:
- Run all tests including Google Drive integration: `python run_tests.py`
- Skip Google Drive tests locally: `python run_tests.py --skip-drive`
- Google Drive tests require valid `client_secret.json` and `token.pickle` files

### Test Categories

| Test File | Description | CI Status |
|-----------|-------------|-----------|
| `test_drive_service.py` | New modular Drive service (well-mocked) | ✅ Runs in CI |
| `test_drive_pictures.py` | Legacy Drive integration | ❌ Skipped in CI |
| `test_integration.py` | Selected integration tests | ⚠️ Partially skipped |

### Running Google Drive Tests Locally

```bash
# Ensure you have Google Drive credentials set up
# 1. Place client_secret.json in project root
# 2. Run app.py once to generate token.pickle via OAuth flow

# Run all tests including Google Drive integration
python run_tests.py

# Run only Google Drive related tests
python -m unittest tests.test_drive_pictures -v
python -m unittest tests.test_integration.TestIntegration.test_drive_integration_with_metadata -v
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure to add the project root to sys.path
2. **Mock Issues**: Ensure mocks are properly configured and match actual APIs
3. **Timeout Issues**: Some integration tests may timeout - use `continue-on-error` for non-critical tests
4. **Platform Differences**: File path separators and line endings may differ across platforms
5. **Google Drive Authentication**: Local tests may fail without proper credentials setup

### Running Tests in Docker

```bash
# Build test environment
docker build -t piframe-test .

# Run tests in container
docker run --rm piframe-test python run_tests.py --no-coverage
```

### Debug Mode

```bash
# Run tests with verbose output and no capture
python -m unittest tests.test_cache_manager -v --buffer

# Run single test with maximum verbosity
python -m unittest tests.test_cache_manager.TestTTLCache.test_set_and_get_basic -v
```

## Contributing

When contributing new features:

1. **Write Tests First**: Follow TDD principles
2. **Maintain Coverage**: Ensure new code has ≥90% test coverage
3. **Update Documentation**: Update this guide if adding new test categories
4. **Run Full Suite**: Ensure all tests pass before submitting PR
5. **Check CI/CD**: Verify all GitHub Actions pass

## Continuous Improvement

The test suite continues to evolve with:
- **Enhanced Coverage**: Adding tests for remaining components
- **Performance Optimization**: Faster test execution
- **Better Mocking**: More realistic test scenarios
- **Cross-Platform Testing**: Ensuring compatibility across environments
- **Security Testing**: Regular vulnerability scans and dependency updates

For questions or issues with testing, please open a GitHub issue with the `testing` label.