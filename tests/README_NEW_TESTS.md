# Testing the Auto-Publish and Version Management Features

## Quick Start

Run all new tests:
```bash
pytest tests/test_version_manager.py tests/test_publish.py tests/test_publish_integration.py -v
```

Expected output: **145 passed in ~1.12s**

## Test Files

### 1. test_version_manager.py (59 tests)
Tests version management for Python, Node.js, Rust, C++, Go, and Ruby projects.

**Run all version manager tests**:
```bash
pytest tests/test_version_manager.py -v
```

**Run specific component tests**:
```bash
# Test version bumping logic
pytest tests/test_version_manager.py::TestVersionBumper -v

# Test Python version management
pytest tests/test_version_manager.py::TestPythonVersionManager -v

# Test Node.js version management
pytest tests/test_version_manager.py::TestNodeVersionManager -v

# Test Rust version management
pytest tests/test_version_manager.py::TestRustVersionManager -v

# Test C++ version management
pytest tests/test_version_manager.py::TestCppVersionManager -v

# Test Go version management (git tags)
pytest tests/test_version_manager.py::TestGoVersionManager -v
```

### 2. test_publish.py (61 tests)
Tests project detection and registry publishing for all supported languages.

**Run all publish tests**:
```bash
pytest tests/test_publish.py -v
```

**Run specific registry tests**:
```bash
# Test project type detection
pytest tests/test_publish.py::TestProjectDetector -v

# Test Python/PyPI publishing
pytest tests/test_publish.py::TestRegistryPublisherPython -v

# Test C++/Conan publishing
pytest tests/test_publish.py::TestRegistryPublisherCpp -v

# Test Node.js/npm publishing
pytest tests/test_publish.py::TestRegistryPublisherNode -v

# Test Rust/crates.io publishing
pytest tests/test_publish.py::TestRegistryPublisherRust -v

# Test Ruby/RubyGems publishing
pytest tests/test_publish.py::TestRegistryPublisherRuby -v

# Test Go/pkg.go.dev publishing
pytest tests/test_publish.py::TestRegistryPublisherGo -v
```

### 3. test_publish_integration.py (25 tests)
Tests full end-to-end workflows combining version bumping and publishing.

**Run all integration tests**:
```bash
pytest tests/test_publish_integration.py -v
```

**Run specific workflow tests**:
```bash
# Test version bumping workflows
pytest tests/test_publish_integration.py::TestPublishIntegrationVersionBumping -v

# Test VFS path resolution
pytest tests/test_publish_integration.py::TestPublishIntegrationVFSPaths -v

# Test dry-run functionality
pytest tests/test_publish_integration.py::TestPublishIntegrationDryRun -v

# Test real-world scenarios
pytest tests/test_publish_integration.py::TestPublishIntegrationRealWorldScenarios -v
```

## Coverage Analysis

**Run tests with coverage**:
```bash
pytest tests/test_version_manager.py tests/test_publish.py tests/test_publish_integration.py \
  --cov=ghops/version_manager --cov=ghops/commands/publish \
  --cov-report=term-missing
```

**Generate HTML coverage report**:
```bash
pytest tests/test_version_manager.py tests/test_publish.py tests/test_publish_integration.py \
  --cov=ghops/version_manager --cov=ghops/commands/publish \
  --cov-report=html

# Open htmlcov/index.html in browser
```

**Expected coverage**:
- `ghops/version_manager.py`: 89%
- `ghops/commands/publish.py`: 96%
- **Combined**: 93%

## Running Specific Tests

### Test a Single Function
```bash
# Test major version bumping
pytest tests/test_version_manager.py::TestVersionBumper::test_bump_major_standard_version -v

# Test Python project detection
pytest tests/test_publish.py::TestProjectDetector::test_detect_python_pyproject_toml -v

# Test complete release workflow
pytest tests/test_publish_integration.py::TestPublishIntegrationRealWorldScenarios::test_complete_release_workflow -v
```

### Test with Pattern Matching
```bash
# Run all tests containing "dry_run" in name
pytest tests/ -k "dry_run" -v

# Run all tests containing "version" in name
pytest tests/ -k "version" -v

# Run all tests containing "publish" but not "integration"
pytest tests/ -k "publish and not integration" -v
```

### Test with Verbose Output
```bash
# Show test names and results
pytest tests/test_version_manager.py -v

# Show test names, results, and print statements
pytest tests/test_version_manager.py -vv

# Show full test output including captured stdout
pytest tests/test_version_manager.py -vv -s
```

## Debugging Failed Tests

### Show Short Traceback
```bash
pytest tests/test_version_manager.py --tb=short
```

### Show Only First Failure
```bash
pytest tests/test_version_manager.py -x
```

### Show First 3 Failures
```bash
pytest tests/test_version_manager.py --maxfail=3
```

### Show Last Failed Tests
```bash
# Re-run only tests that failed last time
pytest tests/test_version_manager.py --lf
```

### Drop into Debugger on Failure
```bash
pytest tests/test_version_manager.py --pdb
```

## Test Organization

### By Functionality
```
Version Management:
  - VersionBumper: Semantic version bumping
  - PythonVersionManager: pyproject.toml, setup.py, __init__.py
  - NodeVersionManager: package.json
  - RustVersionManager: Cargo.toml
  - CppVersionManager: conanfile.py, CMakeLists.txt
  - GoVersionManager: git tags

Project Detection:
  - ProjectDetector: Detect project types from files

Registry Publishing:
  - RegistryPublisher: Publish to various registries
  - PyPI, npm, Conan, crates.io, RubyGems, pkg.go.dev

Integration Workflows:
  - Version bumping + publishing
  - Multi-repo operations
  - VFS path resolution
  - Configuration management
  - Error handling
```

### By Test Type

**Unit Tests** (tests/test_version_manager.py, tests/test_publish.py):
- Test individual functions in isolation
- Mock external dependencies
- Fast execution (~1s for 120 tests)
- High code coverage

**Integration Tests** (tests/test_publish_integration.py):
- Test complete workflows
- Use CLI runner
- Test multiple components together
- Realistic scenarios

## Common Test Patterns

### Creating Test Repositories
```python
def test_example(fs):
    # Create fake repository
    repo_path = "/test/repo"
    fs.create_dir(repo_path)
    fs.create_file(f"{repo_path}/pyproject.toml", contents="...")

    # Test functionality
    result = some_function(repo_path)
    assert result is True
```

### Mocking External Commands
```python
@patch('ghops.commands.publish.run_command')
def test_example(mock_run_command, fs):
    # Setup mock
    mock_run_command.return_value = ("success", 0)

    # Test functionality
    publisher = RegistryPublisher("/test/repo")
    success, message = publisher.publish_python_pypi()

    # Verify mock was called
    assert success is True
    mock_run_command.assert_called_once()
```

### Testing CLI Commands
```python
from click.testing import CliRunner

def test_example(fs):
    runner = CliRunner()
    result = runner.invoke(publish_handler, ['--dry-run'])

    assert result.exit_code == 0
    assert "Dry run" in result.output
```

## Dependencies

Required packages (installed via `pip install -e .`):
- `pytest >= 8.4.1` - Test framework
- `pyfakefs >= 5.10.0` - Fake filesystem
- `pytest-cov >= 6.2.1` - Coverage plugin
- `pytest-mock >= 3.15.1` - Mock helper

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run new feature tests
  run: |
    pytest tests/test_version_manager.py \
           tests/test_publish.py \
           tests/test_publish_integration.py \
           --cov=ghops/version_manager \
           --cov=ghops/commands/publish \
           --cov-report=xml \
           --maxfail=3 \
           -v

- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
```

### Makefile Target
```makefile
.PHONY: test-publish
test-publish:
	pytest tests/test_version_manager.py \
	       tests/test_publish.py \
	       tests/test_publish_integration.py \
	       -v
```

## Test Results Summary

| Test File | Tests | Status | Coverage |
|-----------|-------|--------|----------|
| test_version_manager.py | 59 | ✅ Passing | 89% |
| test_publish.py | 61 | ✅ Passing | 96% |
| test_publish_integration.py | 25 | ✅ Passing | - |
| **Total** | **145** | **✅ All Passing** | **93%** |

## Troubleshooting

### Import Errors
```bash
# Ensure package is installed in development mode
pip install -e .

# Or use PYTHONPATH
PYTHONPATH=/home/spinoza/github/beta/ghops pytest tests/
```

### Fake Filesystem Issues
```bash
# If tests fail with "No such file or directory"
# Check that test uses the 'fs' fixture
def test_example(fs):  # <-- Must have 'fs' parameter
    fs.create_dir("/test/repo")
```

### Mock Not Working
```bash
# Ensure you're mocking the right module
# Mock where it's imported, not where it's defined
@patch('ghops.commands.publish.run_command')  # ✅ Correct
@patch('ghops.utils.run_command')             # ❌ Wrong
```

## Next Steps

1. **Run the tests**: `pytest tests/test_version_manager.py tests/test_publish.py tests/test_publish_integration.py -v`
2. **Check coverage**: Add `--cov` flags as shown above
3. **Add to CI**: Use the GitHub Actions example
4. **Manual testing**: Test with real PyPI/npm/etc. registries

## Resources

- [TESTING_SUMMARY.md](../TESTING_SUMMARY.md) - Detailed test documentation
- [pytest documentation](https://docs.pytest.org/) - pytest usage
- [pyfakefs documentation](https://pytest-pyfakefs.readthedocs.io/) - Fake filesystem
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html) - Python mocking
