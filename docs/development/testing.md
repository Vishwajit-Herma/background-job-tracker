# Testing & Code Quality

Background Job Tracker enforces automated test coverage and strict linting standards across the backend, frontend, and Python SDK.

---

## 🧪 Backend Tests (pytest)

Run the Django backend test suite:

```bash
# Run all backend tests
uv run pytest

# Run with verbose output and coverage
uv run pytest -v --cov=apps

# Run a specific test module
uv run pytest apps/incidents/tests/
```

---

## 🎨 Backend Linting & Formatting (Ruff)

All Python code must satisfy Ruff linting and formatting rules:

```bash
# Check linting errors
uv run ruff check .

# Fix auto-fixable lint issues
uv run ruff check --fix .

# Verify code formatting
uv run ruff format --check .
```

---

## 📦 SDK Tests

The Python SDK includes a dedicated test suite verifying signals, batching, and Celery prefork safety:

```bash
cd sdk

# Install dev dependencies
pip install -e ".[all,dev]"

# Run SDK unit tests
pytest
```

---

## 💻 Frontend Verification

Verify TypeScript compilation and ESLint rules in the Next.js frontend:

```bash
cd frontend

# TypeScript typecheck
npx tsc --noEmit

# ESLint validation
npm run lint
```
