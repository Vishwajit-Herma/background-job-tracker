# Architecture Overview

Background Job Tracker follows a modern Django architecture with clean separation of concerns and production-ready patterns.

## Project Structure

```
background_job_tracker/
├── apps/                   # Django applications
│   ├── core/              # Core functionality (health checks, utils, middleware)
│   ├── users/             # Custom user model and authentication
│   ├── api/               # API endpoints (DRF)
│   ├── teams/             # Multi-tenancy (teams, invitations, RBAC)
│   └── ...                # Additional apps as needed
├── config/                 # Project configuration
│   ├── settings/          # Split settings (base, dev, test, prod)
│   ├── urls.py            # URL configuration
│   ├── asgi.py            # ASGI application
│   └── wsgi.py            # WSGI application
├── static/                 # Static files (CSS, JS, images)
├── media/                  # User uploads
├── docs/                   # Project documentation
│   ├── getting-started/   # Setup and first steps
│   ├── architecture/      # This overview
│   └── development/       # Testing and workflow
├── tests/                  # Test suite
├── deploy/                 # Deployment configurations
│   └── k8s/               # Kubernetes (Helm + Kustomize)
├── .github/
│   └── workflows/         # GitHub Actions CI/CD
├── Dockerfile             # Production container image
├── docker-compose.yml     # Development environment
├── Justfile               # Task runner (commands)
├── pyproject.toml         # Python dependencies and tool config
└── README.md
```

## Key Components

### Django Apps

- **core**: Core functionality shared across the project
  - Health check endpoints (`/health/`)
  - Middleware (security, logging, team context)
  - Utility functions and helpers
- Celery tasks
- **users**: Custom user model and authentication
  - Email-based authentication
  - User profile management
- Social authentication (Google, GitHub, etc.)
- User impersonation for staff support

- **api**: API layer
- RESTful endpoints (Django REST Framework)
  - OpenAPI/Swagger documentation
  - Serializers and viewsets
- Authentication (session + token)
  - Permissions and throttling

- **teams**: Multi-tenancy and team management
  - Team model with RBAC (Owner, Admin, Member)
  - Team invitations with email verification
  - Team-scoped data access
  - Per-team billing
  - Audit logging

### Settings Architecture

Settings are environment-specific and split across files:

- **`base.py`**: Common settings for all environments
  - Installed apps and middleware
  - Database and cache configuration
  - Static and media file handling
  - Security settings (CSRF, headers, allowed hosts)

- **`dev.py`**: Development overrides
  - `DEBUG = True`
  - Django Debug Toolbar
  - Permissive CORS for local frontend development
  - Email backend → Mailpit (console)

- **`test.py`**: Test configuration
  - In-memory database for speed
  - Disabled migrations where safe
  - Test-specific settings

- **`prod.py`**: Production hardening
  - `DEBUG = False`
  - Strict security headers (CSP, HSTS)
  - Gunicorn WSGI server
- Sentry error tracking
- OpenTelemetry tracing
### Deployment

#### Kubernetes (Enterprise)
- **Charts**: Helm for templated deployments
- **Overlays**: Kustomize for environment-specific configs
- **Features**: HPA, ingress, service mesh ready
- **Database**: CloudNativePG operator for PostgreSQL
- **Monitoring**: Prometheus + Grafana stack
- **Best for**: Enterprise scale, multi-cluster, advanced orchestration

## Data Flow

### Request/Response Flow

```
User Request
     ↓
Load Balancer (ALB/Ingress)
     ↓
Django Middleware Stack
     ├─ SecurityMiddleware (headers, SSL redirect)
     ├─ SessionMiddleware (session management)
     ├─ AuthenticationMiddleware (user authentication)
├─ TeamContextMiddleware (team scoping)
└─ WaffleMiddleware (feature flags)
     ↓
URL Router
     ↓
View / API Endpoint
     ├─ Permission Checks
├─ Business Logic
     ├─ Database Queries (PostgreSQL)
├─ Cache Lookups (Redis)
└─ Background Tasks (Celery)
↓
Serialization / Template Rendering
     ↓
Response (JSON)
```

### Background Task Flow

```
View/API triggers task
     ↓
Celery.delay() → Redis (broker)
     ↓
Celery Worker picks up task
     ↓
Task execution
     ├─ Database operations
     ├─ External API calls
     └─ Email sending
     ↓
Result stored in Redis (backend)
     ↓
Status available via Flower dashboard
```

## Security Architecture

### Authentication & Authorization

1. **User Authentication**
- Email/password via django-allauth
   - Social OAuth (Google, GitHub, etc.)
2. **Authorization**
- Team-based permissions (Owner → Admin → Member)
   - Per-resource access control
- Django permissions system
   - Custom decorators for view protection

3. **Security Headers**
   - Content Security Policy (CSP)
   - HTTP Strict Transport Security (HSTS)
   - X-Frame-Options (Clickjacking protection)
   - X-Content-Type-Options (MIME sniffing protection)
4. **Input Validation**
   - Django form validation
- DRF serializer validation
- CSRF token protection
## Database Design

### Core Tables

- `users_user`: Custom user model (email-based)
- `teams_team`: Organization/team model
- `teams_teammember`: Many-to-many with role
- `teams_teaminvitation`: Pending invitations
- `waffle_*`: Feature flag tables

### Indexing Strategy

- Foreign keys automatically indexed
- Email fields (unique + indexed)
- Team scoping queries optimized
- Composite indexes for common query patterns

## Observability

### Logging
- **Format**: Structured JSON logs
- **Levels**: DEBUG → INFO → WARNING → ERROR → CRITICAL
- **Context**: Request ID, user ID, team ID
- **Aggregation**: OpenTelemetry → Logging backend
### Monitoring
- **Error Tracking**: Sentry (real-time error alerts)
- **Metrics**: Prometheus (custom metrics + Django metrics)
- **Dashboards**: Grafana (pre-built dashboards)
- **Tracing**: OpenTelemetry (distributed request tracing)
- **APM**: Application performance monitoring
- **Health Checks**: `/health/` endpoint (database, cache, Redis)

## Performance Optimization

### Caching Strategy
- **Backend**: Redis
- **Cached Data**:
  - Database query results (per-view caching)
  - API responses (DRF throttling)
- Team permissions (avoid repeated DB lookups)
- Template fragments
- **Cache Invalidation**: Signals on model save/delete
### Database Optimization
- Connection pooling (production)
- Select/prefetch related for N+1 prevention
- Database indexes on frequently queried fields
- Query optimization with Django Debug Toolbar (dev)

### Static Files
- **Storage**: Local filesystem (development)
- **Production**: WhiteNoise for efficient static serving
- **Compression**: Gzip/Brotli enabled
- **Cache Headers**: Long expiry for static assets

## Design Decisions

### Why Split Settings?
- **Environment isolation**: Dev settings differ from prod
- **Security**: Secrets never in version control
- **Flexibility**: Easy to override per-environment
- **Testing**: Optimized test configuration

### Why Custom User Model?
- **Email-based**: More modern than username
- **Future-proof**: Easy to extend without migrations
- **Django best practice**: Recommended in official docs

### Why uv over Poetry?
- **Speed**: 10-100x faster dependency resolution
- **Simplicity**: Single binary, no Python dependency
- **Standards**: Uses pyproject.toml (PEP 621)
- **Compatibility**: Works with existing Poetry projects
### Why Celery?
- **Battle-tested**: Production-ready background tasks
- **Scalable**: Horizontal worker scaling
- **Monitoring**: Flower dashboard included
- **Flexible**: Supports periodic tasks, chains, chords
### Why Helm + Kustomize?
- **Helm**: Package management, versioning, rollbacks
- **Kustomize**: Environment-specific configs (GitOps-friendly)
- **Together**: Best of both worlds (templating + patching)
## Further Reading

- [Getting Started](../getting-started/installation.md)
- [Development Guide](../development/testing.md)
