# Background Job Tracker

Welcome to the Background Job Tracker documentation!

## Overview

A Django Project to track Background jobs.

## Features

### Core
- **Django 6.0** with Python 3.14
- **Package Management**: uv
- **Database**: postgresql with connection pooling
- **Caching**: Redis for high performance
- **Authentication**: django-allauth (social + email)
### API & Frontend
- **API Framework**: Django REST Framework with OpenAPI/Swagger docs
### Background Tasks & Real-time
- **Background Jobs**: Celery with Redis broker
- **Periodic Tasks**: Celery Beat for scheduled jobs
- **Monitoring**: Flower dashboard for task monitoring
### SaaS Features
- **Multi-Tenancy**: Teams & organizations with RBAC
- **Team Roles**: Owner, Admin, Member permissions
- **Team Invitations**: Email-based with secure tokens
- **Feature Flags**: django-waffle for A/B testing and gradual rollouts
- **User Impersonation**: Staff can impersonate users for support/debugging

### Observability & Monitoring
- **Error Tracking**: Sentry + distributed tracing
- **Structured Logging**: JSON logs with correlation IDs
- **Metrics**: Prometheus + Grafana dashboards
- **APM**: Application Performance Monitoring
- **Health Checks**: `/health/` endpoint with database connectivity checks
### Security
- **Security Headers**: CSP, HSTS, X-Frame-Options
- **Password Security**: Argon2 hashing
- **CSRF Protection**: Built-in Django CSRF + SameSite cookies
### Development Tools
- **Task Runner**: Justfile for common commands
- **Code Quality**: Ruff for linting and formatting
- **Type Checking**: mypy for static type analysis
- **Testing**: pytest with coverage reporting
- **Pre-commit Hooks**: Automated code quality checks
- **CI/CD**: GitHub Actions
### Deployment
- **Kubernetes**: Helm charts + Kustomize overlays for GitOps
- **Production Ready**: Environment-based configuration, database migrations, static file serving

## Quick Start

```bash
# Clone the repository
git clone https://github.com/Vishwajit-Herma/background-job-tracker
cd background_job_tracker

# Install dependencies
uv sync


# Start development services
docker compose up -d

# Run migrations
just migrate

# Create superuser
just createsuperuser

# Start development server
just dev
```

## Access Points

After starting the development server:

- **Application**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin/
- **API Documentation**: http://localhost:8000/api/schema/swagger/
- **Email Testing (Mailpit)**: http://localhost:8025
- **Celery Flower**: http://localhost:5555 (after running `just celery-flower`)
## Next Steps

- [Installation Guide](getting-started/installation.md) - Detailed setup instructions
- [Architecture Overview](architecture/overview.md) - System design and structure
- [Development Guide](development/testing.md) - Testing and development workflow

For deployment, see the platform guides in the `deploy/` directory of this repository.

## Documentation

Browse the full documentation:

- **Getting Started**: Installation and first steps
- **Architecture**: System design, project structure, key decisions
- **Development**: Testing, debugging, workflow

---

**Built with [Django Keel](https://github.com/CuriousLearner/django-keel)** 🚢
