<div align="center">

# ⚡ Background Job Tracker (BJT)

**Developer-first observability, real-time telemetry, AI-assisted incident response, and reliability intelligence for background tasks.**

🌐 **Live Platform:** [BJT](https://background-job-tracker-wine.vercel.app/)

[![Documentation](https://img.shields.io/badge/docs-readthedocs.io-blue.svg)](https://background-job-tracker.readthedocs.io/en/latest/)
[![PyPI Version](https://img.shields.io/pypi/v/background-job-tracker?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/background-job-tracker/)
[![Python Versions](https://img.shields.io/pypi/pyversions/background-job-tracker?logo=python&logoColor=white)](https://pypi.org/project/background-job-tracker/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js&logoColor=white)](https://nextjs.org/)
[![Django](https://img.shields.io/badge/Django-6.x-0C4B33?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Celery](https://img.shields.io/badge/Celery-5.0+-brightgreen.svg?logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

[Live App](https://background-job-tracker-wine.vercel.app/) • [📖 Documentation (ReadTheDocs)](https://background-job-tracker.readthedocs.io/en/latest/) • [Python SDK on PyPI](https://pypi.org/project/background-job-tracker/) • [Report Bug / Request Feature](https://github.com/Vishwajit-Herma/background-job-tracker/issues)

</div>

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
  - [⚡ Non-Blocking SDK Telemetry](#-non-blocking-zero-impact-sdk)
  - [🤖 AI Reliability Assistant & Deep Investigation](#-ai-reliability-assistant--deep-investigation)
  - [🚨 Incident Management, Assignment & Runbooks](#-incident-management-assignment--runbooks)
  - [📊 Real-Time Metrics & Observability](#-automated-task-discovery--observability)
  - [🏢 Enterprise Multi-Tenancy & Security](#-enterprise-multi-tenancy--security)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [Repository Structure](#-repository-structure)
- [Quickstart: Local Development](#-quickstart-local-development)
  - [1. Start Full Backend via Docker Compose](#1-start-full-backend-via-docker-compose)
  - [2. Start Frontend Dashboard](#2-start-frontend-dashboard)
- [SDK Quickstart](#-sdk-quickstart)
  - [Celery Integration (Django, FastAPI, Flask, Standalone)](#1-celery-integration)
  - [Python RQ Integration](#2-python-rq-integration)
- [Documentation](#-documentation)
- [Testing & Code Quality](#-testing--code-quality)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🚀 Overview

Background task queues (Celery, Python RQ, etc.) are critical to modern applications, handling asynchronous workloads such as email delivery, payment processing, report generation, data pipelines, and AI inferencing. However, when background workers fail, silently retry, suffer memory leaks, or experience queue stalls, traditional APMs often provide delayed or opaque insights.

**Background Job Tracker (BJT)** is an end-to-end reliability platform that provides:
1. **Real-time execution telemetry** from background workers with zero performance impact.
2. **Automated incident detection** for failure spikes, latency anomalies, and stalled queues.
3. **AI-Powered Incident Investigation** with strictly-grounded execution traceback analysis and automated root-cause suggestions.
4. **Team incident assignment & response** with interactive mitigation runbooks and postmortems.
5. **Centralized multi-tenant dashboard** with rich analytics, queue latencies, percentile breakdowns ($p50$, $p95$, $p99$), and team collaboration.

> 💡 **Core Architectural Principle:** BJT does **not** execute your customer jobs or act as a task broker. Your application owns its task execution; BJT owns deep observability, telemetry ingestion, reliability analysis, incident detection, AI diagnosis, and alerting.

---

## ✨ Key Features

### ⚡ Non-Blocking, Zero-Impact SDK
- **Microsecond Ingestion:** Signals perform non-blocking memory queue enqueues.
- **Process-Fork Safety:** Automatically detects process forks (e.g. Celery `prefork` pool) to spawn isolated worker queues and background daemon sender threads per PID.
- **Fail-Safe & Memory Bounded:** Telemetry network errors, timeouts, or backend outages never crash your customer-facing worker tasks.

### 🤖 AI Reliability Assistant & Deep Investigation
- **Grounded Traceback & Telemetry Analysis:** Evaluates representative failed executions, stack traces, application frames, worker hostnames, and queue metrics to diagnose incidents.
- **Strict Evidence Citation:** Categorizes facts by source (`incident`, `execution`, `analytics`, `reliability`, `runbook`, `postmortem`) and distinguishes observed facts from inferred conclusions.
- **Confidence Scoring:** Automatically assigns confidence ratings (`HIGH`, `MEDIUM`, `LOW`, `INSUFFICIENT_EVIDENCE`) based on available data completeness.
- **Actionable Remediation Guidance:** Returns targeted investigation steps and operational actions grounded in empirical telemetry.

### 🚨 Incident Management, Assignment & Runbooks
- **Automated Incident Triggers:** Detects abnormal error rates, consecutive task crashes, and duration SLA breaches.
- **Team Assignment & Triage:** Assign open incidents directly to team members, track owner responders, and manage state transitions (`Open` $\rightarrow$ `Acknowledged` $\rightarrow$ `Resolved`).
- **Interactive Runbooks:** Attach step-by-step mitigation playbooks (manual or automated) directly to incident workflows.
- **Postmortems & Audit Timelines:** Document confirmed root causes, trigger causes, and preventive actions alongside complete chronological activity logs.

### 🔍 Automated Task Discovery & Observability
- **Automatic Task Registration:** Discovers task signatures, queues, and worker hostnames upon worker initialization.
- **Execution Lifecycle Tracking:** Captures duration, runtime arguments, exception traces, retry counts, queue wait latency, and custom metadata.
- **Percentile Performance Breakdown:** Real-time visibility into $p50$, $p90$, $p95$, and $p99$ execution durations.

### 🏢 Enterprise Multi-Tenancy & Security
- **Multi-Tenant Workspaces:** Strict team isolation, granular role-based access control (`Owner`, `Admin`, `Member`), and team invitations.
- **Scoped API Keys:** Secure SHA-256 hashed API keys per project environment.
- **Multi-Channel Alerting:** Dispatch incident notifications across Email, HMAC-signed Webhooks, and In-App real-time alerts.

---

## 🏗️ System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                    Customer App & Worker Fleet                          │
│                                                                         │
│   [ Celery / RQ Task Workers ]                                          │
│         │                                                               │
│         ▼  (Worker signals: prerun / success / failure / retry)         │
│   [ BJT Python SDK (background-job-tracker) ]                           │
│         │                                                               │
│         ▼  (Non-blocking put_nowait)                                    │
│   ┌───────────────────────────────────┐                                 │
│   │   Bounded In-Memory Queue         │                                 │
│   └─────────────────┬─────────────────┘                                 │
│                     │ (Daemon batch drain)                              │
│                     ▼                                                   │
│   ┌───────────────────────────────────┐                                 │
│   │   Background Daemon Sender Thread │                                 │
│   │   - Batching & Backoff Retry      │                                 │
│   └─────────────────┬─────────────────┘                                 │
└─────────────────────┼───────────────────────────────────────────────────┘
                      │
                      │ HTTPS POST (/api/executions/ingest/)
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Background Job Tracker Platform                      │
│                                                                         │
│   [ Django REST Ingestion API ] ──► [ Redis Broker & Cache ]            │
│                                                 │                       │
│                                                 ▼                       │
│                                   [ BJT Background Workers ]            │
│                                   - Real-time stream processing         │
│                                   - Anomaly & Incident engine           │
│                                                 │                       │
│                  ┌──────────────────────────────┴────────────────────┐  │
│                  ▼                              ▼                    ▼  │
│   [( PostgreSQL DB )]        [ AI Reliability Engine ]      [ Alerts ]  │
│   - Tasks & Executions       - Incident Investigation       - Email     │
│   - Incidents & Assignments  - Traceback Analysis           - Webhooks  │
│   - Runbooks & Postmortems   - Grounded Evidence & Plan     - In-App    │
│   - Teams & API Keys                        │                           │
│                  ▲                          │                           │
│                  │                          │                           │
│                  ▼                          ▼                           │
│   [ Next.js 15 Web Dashboard & Real-Time Engine ]                       │
│   - Incident assignment, triage, runbooks, and timeline audit logs      │
│   - Real-time execution logs, p50/p95/p99 analytics, and dark mode      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Domain | Technologies |
|---|---|
| **Backend API** | Python 3.14, Django 6.x, Django REST Framework, PostgreSQL, Redis, Celery, Celery Beat |
| **AI Engine** | AI Reliability Assistant (Grounded telemetry reasoning & structured investigation outputs) |
| **Package Management** | `uv` (Fast Python package installer and resolver) |
| **API Documentation** | OpenAPI 3.0 via `drf-spectacular` / Swagger UI / Redoc |
| **Frontend Dashboard** | Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, TanStack Query, Radix UI, Lucide Icons |
| **Python SDK** | Python 3.8 – 3.13 (`background-job-tracker` on PyPI) |
| **Infrastructure** | Docker & Docker Compose |

---

## 📁 Repository Structure

```text
.
├── apps/                               # Django backend applications
│   ├── ai/                             # AI Reliability Assistant (incident investigation & evidence reasoning)
│   ├── alerts/                         # Alert rules, thresholds, policies, and notification dispatch
│   ├── api/                            # Central DRF routers, OpenAPI schema, authentication endpoints
│   ├── config_management/              # System configurations and response formatters
│   ├── core/                           # Base models, tenancy utilities, audit logging, realtime tickets
│   ├── executions/                     # High-throughput execution ingestion pipeline & telemetry models
│   ├── incidents/                      # Incident lifecycle, team assignment, triage, runbooks, postmortems
│   ├── jobs/                           # Task registry, health scoring, duration percentiles (p50/p95/p99)
│   ├── notifications/                  # Notification delivery channels (Email, HMAC Webhooks, In-App)
│   ├── projects/                       # Multi-environment project scoping and hashed API key management
│   ├── reliability/                    # Aggregated reliability metrics, SLA tracking, and throughput
│   ├── teams/                          # Multi-tenant workspaces, team members, invitations, and RBAC
│   └── users/                          # User accounts, profiles, and django-allauth adapters
├── config/                             # Django settings, ASGI/WSGI, and Celery dogfooding config
├── docs/                               # Architecture, API specifications, and design guidelines
├── frontend/                           # Next.js 15 modern web application
│   ├── app/                            # Next.js App Router (dashboard, auth, settings, onboarding)
│   ├── components/                     # Reusable UI components, design system, widgets
│   │   ├── bjt/                        # BJT domain components (incidents, jobs, reliability, runbooks)
│   │   └── ui/                         # Base UI primitives (buttons, dialogs, dropdowns, inputs)
│   ├── hooks/                          # Custom React hooks (useAuth, useDebounce, etc.)
│   └── lib/                            # API clients, TanStack Query hooks, and TypeScript types
├── sdk/                                # Official Python SDK (background-job-tracker on PyPI)
│   ├── background_job_tracker/         # Core Tracker client, bounded queue, and daemon sender thread
│   ├── integrations/                   # Drop-in Celery and RQ integrations
│   └── tests/                          # SDK unit, integration, and fork-safety test suite
├── static/                             # Backend static files and brand assets
├── templates/                          # Django email and authentication HTML templates
├── tests/                              # Comprehensive backend test suite (pytest)
├── docker-compose.yml                  # Multi-container Docker configuration (API, DB, Redis, Celery, Mailpit)
├── Justfile                            # Command runner shortcuts
└── pyproject.toml                      # Backend dependencies and ruff linting configuration
```

---

## 🚀 Quickstart: Local Development

### Prerequisites
- [Docker & Docker Compose](https://docs.docker.com/get-docker/)
- [Node.js 18+](https://nodejs.org/) & `npm` (for frontend)

---

### 1. Start Full Backend via Docker Compose

Run the entire backend stack (API, PostgreSQL, Redis, Celery Worker, Celery Beat, Mailpit) with a single command:

```bash
# 1. Clone the repository
git clone https://github.com/Vishwajit-Herma/background-job-tracker.git
cd background-job-tracker

# 2. Copy environment variables
cp .env.example .env

# 3. Start all backend containers
docker compose up -d

# 4. Run database migrations & create an admin superuser
docker compose exec web uv run python manage.py migrate
docker compose exec web uv run python manage.py createsuperuser
```

#### Services Available:
- **Django API & Swagger Docs:** [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/)
- **Mailpit Web UI (Email capture):** [http://localhost:8025](http://localhost:8025)

---

### 2. Start Frontend Dashboard

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to access the interactive web dashboard.

---

## 🔌 SDK Quickstart

Install the official SDK from PyPI:

```bash
pip install background-job-tracker
```

### 1. Celery Integration

Add 3 lines to your `celery.py`:

```python
import os
from celery import Celery
from background_job_tracker import Tracker
from background_job_tracker.integrations.celery import CeleryIntegration

app = Celery("my_app")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Initialize Tracker SDK
tracker = Tracker(
    api_key=os.environ["BACKGROUND_JOB_TRACKER_API_KEY"],
    base_url=os.getenv("BACKGROUND_JOB_TRACKER_BASE_URL", "https://app.jobtracker.io"),
)
CeleryIntegration(app=app, tracker=tracker)
```

### 2. Python RQ Integration

Attach the integration to your worker:

```python
import os
from redis import Redis
from rq import Worker, Queue
from background_job_tracker import Tracker
from background_job_tracker.integrations.rq import RQIntegration

tracker = Tracker(api_key=os.environ["BACKGROUND_JOB_TRACKER_API_KEY"])
rq_integration = RQIntegration(tracker=tracker, modules=["my_app.tasks"])

if __name__ == "__main__":
    redis_conn = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    worker = Worker([Queue("default", connection=redis_conn)], connection=redis_conn)
    rq_integration.attach(worker)
    worker.work()
```

---

## 📚 Documentation

The full documentation is hosted online at **[https://background-job-tracker.readthedocs.io/en/latest/](https://background-job-tracker.readthedocs.io/en/latest/)**.

You can also browse the markdown source guides in the [`docs/`](docs/) directory:

| Topic | Guide | Description |
|---|---|---|
| **Getting Started** | [`docs/getting-started/installation.md`](docs/getting-started/installation.md) | Full local installation instructions and service ports. |
| **SDK Quickstart** | [`docs/getting-started/sdk-quickstart.md`](docs/getting-started/sdk-quickstart.md) | SDK setup for Celery, Python RQ, and custom worker scripts. |
| **AI Reliability** | [`docs/features/ai-reliability-assistant.md`](docs/features/ai-reliability-assistant.md) | Grounded incident investigation and traceback analysis. |
| **Incidents & Runbooks** | [`docs/features/incident-management.md`](docs/features/incident-management.md) | Incident assignment, lifecycle states, runbooks, and postmortems. |
| **Alerts & Notifications** | [`docs/features/alerting-and-notifications.md`](docs/features/alerting-and-notifications.md) | Alert rule thresholds, webhook signatures, and email delivery. |
| **System Architecture** | [`docs/architecture/overview.md`](docs/architecture/overview.md) | Deep dive into the non-blocking telemetry ingestion pipeline. |
| **Domain Model** | [`docs/architecture/domain-model.md`](docs/architecture/domain-model.md) | Entity relationships, multi-tenancy, and data models. |
| **Testing Guide** | [`docs/development/testing.md`](docs/development/testing.md) | Running backend pytest suites, SDK tests, and linters. |

---

## 🧪 Testing & Code Quality

### Backend & Core Tests
```bash
# Run Django test suite with pytest
uv run pytest

# Check code formatting & linting with ruff
uv run ruff check .
uv run ruff format --check .
```

### SDK Tests
```bash
cd sdk
pytest
```

### Frontend Verification
```bash
cd frontend
npx tsc --noEmit
npm run lint
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:
1. Fork the repository.
2. Create a descriptive feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes following standard commit conventions.
4. Ensure all automated tests and linter checks pass.
5. Push to the branch and open a Pull Request.

---

## 📄 License

This project is open-source software licensed under the [MIT License](LICENSE).
