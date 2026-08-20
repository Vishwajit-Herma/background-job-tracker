# Installation

This guide will help you get Background Job Tracker up and running.

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- Docker & Docker Compose
- PostgreSQL (for production)
- Redis


## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/CuriousLearner/django-keel
cd background_job_tracker
```

### 2. Install Dependencies

```bash
uv sync
```


### 3. Environment Configuration

```bash
cp .env.example .env
# Edit .env with your settings
```

### 4. Start Services

```bash
docker compose up -d
```

This starts:
- PostgreSQL
- Redis
- Mailpit (email testing)

### 5. Database Setup

```bash
just migrate
just createsuperuser
```

### 6. Start Development Server

```bash
just dev
```

Visit:
- Application: http://localhost:8000
- Admin: http://localhost:8000/admin/
- API Docs: http://localhost:8000/api/schema/swagger/
- Mailpit: http://localhost:8025

## Next Steps

- [Architecture Overview](../architecture/overview.md)
- [Testing Guide](../development/testing.md)
