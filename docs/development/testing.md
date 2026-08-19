# Testing Guide

This project uses pytest for testing with comprehensive test coverage.

## Running Tests

### Quick Start

```bash
# Run all tests
just test

# Run with coverage report
uv run pytest --cov


# Run specific test file
uv run pytest tests/test_users.py


# Run specific test function
uv run pytest tests/test_users.py::test_create_user

```

### Test Options

```bash
# Run tests in parallel
uv run pytest -n auto


# Run tests with verbose output
uv run pytest -v


# Stop on first failure
uv run pytest -x


# Run only failed tests from last run
uv run pytest --lf

```

## Test Structure

Tests are organized in the `tests/` directory:

```
tests/
├── conftest.py              # Pytest fixtures and configuration
├── test_core.py             # Core functionality tests
├── test_users.py            # User model and authentication tests
├── test_api.py              # API endpoint tests
├── test_tasks.py            # Celery task tests
└── __init__.py
```

## Available Fixtures

### Common Fixtures

- `client` - Django test client
- `user` - Standard test user
- `admin_user` - Admin/superuser for testing
- `multiple_users` - List of test users

### API Fixtures

- `api_client` - DRF API client (unauthenticated)
- `authenticated_api_client` - API client with authenticated user
- `admin_api_client` - API client with admin user

### Authentication Fixtures

- `verified_user` - User with verified email address

## Writing Tests

All tests are function-based and use pytest markers:

```python
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_create_user():
    """Test creating a user."""
    user = User.objects.create_user(email="test@example.com", password="testpass123")
    assert user.email == "test@example.com"
    assert user.is_active
    assert not user.is_staff
```

### Test Naming Convention

- Test files: `test_*.py`
- Test functions: `test_*`
- Use descriptive names that explain what is being tested

### Using Fixtures

```python
@pytest.mark.django_db
def test_user_can_login(client, user):
    """Test that a user can log in."""
    logged_in = client.login(username=user.email, password="testpass123")
    assert logged_in
```

### API Testing

```python
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
def test_api_endpoint(authenticated_api_client):
    """Test API endpoint."""
    url = reverse("api-endpoint-name")
    response = authenticated_api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert "expected_field" in response.json()
```

### Testing Celery Tasks

```python
from apps.core.tasks import example_task


@pytest.mark.django_db
def test_celery_task():
    """Test Celery task execution."""
    result = example_task.delay()
    assert result is not None
```

## Test Coverage

### Generating Coverage Reports

```bash
# HTML coverage report
uv run pytest --cov --cov-report=html


# Open coverage report
open htmlcov/index.html
```

### Coverage Targets

- Overall coverage: 80%+
- Critical paths: 90%+
- New code: 100%

## Continuous Integration

Tests run automatically on every push via GitHub Actions.

### CI Workflow

1. Lint and format checks
2. Type checking with mypy
3. Test execution with coverage
4. Coverage report upload

## Best Practices

### DO

- ✅ Write tests for all new features
- ✅ Test both success and failure cases
- ✅ Use descriptive test names
- ✅ Keep tests independent
- ✅ Use fixtures for common setup
- ✅ Test edge cases

### DON'T

- ❌ Write class-based tests (use functions)
- ❌ Test implementation details
- ❌ Depend on test execution order
- ❌ Use real external services (use mocks)
- ❌ Skip writing tests for "simple" code

## Debugging Tests

### Using pdb

```python
@pytest.mark.django_db
def test_something():
    import pdb

    pdb.set_trace()  # Debugger will stop here
    # ... test code
```

### Print debugging

```bash
# Show print statements
uv run pytest -s

```

### Verbose output

```bash
# Show detailed test output
uv run pytest -vv

```

## Further Reading

- [pytest documentation](https://docs.pytest.org/)
- [pytest-django documentation](https://pytest-django.readthedocs.io/)
- [DRF testing](https://www.django-rest-framework.org/api-guide/testing/)
- [Django testing](https://docs.djangoproject.com/en/6.0/topics/testing/)
