# Architecture Overview

Background Job Tracker is designed for high-throughput, low-latency telemetry ingestion, robust multi-tenancy, and automated incident response.

---

## 🏗️ High-Level System Design

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

## ⚡ Non-Blocking Telemetry Pipeline

1. **Microsecond Enqueue:** When tasks execute, worker signal handlers place telemetry events into an in-memory `queue.Queue`.
2. **Asynchronous Daemon Thread:** A dedicated daemon thread flushes batches over HTTP/HTTPS.
3. **Bounded Memory Protection:** If network connectivity to BJT is lost, the queue drops events when reaching capacity (`max_queue_size=10000`) rather than consuming worker memory or blocking task execution.
4. **Process-Fork Safety:** The SDK detects PID changes in forked child processes (such as Celery's `prefork` pool) and spawns an isolated queue and sender thread per worker process.

---

## 🏢 Tenancy & Data Isolation

Multi-tenancy is enforced at the database and query layer:
- **Teams:** Represent customer organizations. Every user belongs to one or more teams with roles (`Owner`, `Admin`, `Member`).
- **Projects:** Applications or environments (e.g. `production`, `staging`) belonging to a Team.
- **API Keys:** Scoped to individual projects using secure SHA-256 hashes.
- **Server-Side Isolation:** All querysets enforce team and project tenant scoping so Team A can never view or manipulate Team B's telemetry or incidents.
