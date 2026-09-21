# Changelog

All notable changes to Background Job Tracker will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project setup generated with django-keel
- Django 6.0 with Python 3.14
- Django REST Framework API
- Celery background task queue with Redis broker
- Kubernetes deployment configuration (Helm + Kustomize)
- Comprehensive pytest test suite
  - Core functionality tests
  - User authentication tests
- API endpoint tests
- Celery task tests
## [0.1.0] - YYYY-MM-DD

### Added
- Initial release
- Core Django setup with custom user model
- Authentication system with django-allauth
- postgresql database configuration
- Redis caching
- Local media storage with Whitenoise
- Observability stack:
  - Structured logging
  - Prometheus metrics
- Development tooling:
  - Ruff for linting and formatting
  - mypy for type checking
  - pre-commit hooks
- GitHub Actions CI/CD
- Docker Compose development environment
- MkDocs documentation

[Unreleased]: https://github.com/Vishwajit-Herma/background-job-tracker/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Vishwajit-Herma/background-job-tracker/releases/tag/v0.1.0
