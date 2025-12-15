# Integration Tests

This directory contains integration tests for ArchiFlow components.

## Purpose

Integration tests verify that multiple components work together correctly. Unlike unit tests that test individual components in isolation, integration tests test the full workflow from end to end.

## Running Tests

### Individual Test
```bash
cd integration_tests
python test_simplev2_integration.py
```

### All Tests (using pytest)
```bash
pytest integration_tests/
```

## Test Files

- `test_simplev2_integration.py`: Tests for SimpleAgent v2 integration with the agent factory and REPL interface

## Adding New Integration Tests

1. Create a new test file named `test_<feature>_integration.py`
2. Follow the existing pattern:
   - Import necessary modules
   - Add the src directory to Python path
   - Create test functions that start with `test_`
   - Use descriptive function names
   - Include clear success/failure indicators

Example:
```python
#!/usr/bin/env python3
"""Integration test for new feature."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_feature():
    """Test the new feature integration."""
    # Test implementation here
    pass

if __name__ == "__main__":
    # Run test
    result = test_feature()
    print(f"[{'PASS' if result else 'FAIL'}] Feature integration test")
```

## Test Organization

- Keep tests focused on integration between components
- Avoid mocking real components unless necessary
- Test realistic user scenarios
- Include setup and cleanup if needed