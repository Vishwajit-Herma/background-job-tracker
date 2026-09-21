# Background Job Tracker (BJT) Documentation

Welcome to the **Background Job Tracker** documentation!

BJT is an end-to-end reliability, telemetry, and automated incident response platform specifically built for background tasks and worker queues (Celery, Python RQ, and custom Python workers).

---

## 🎯 What Problem Does BJT Solve?

Modern applications rely heavily on background task queues for asynchronous processing—ranging from transactional emails and PDF generation to batch billing and machine learning inferencing. 

However, background workers operate as opaque black boxes:
- **Silent Failures:** Tasks fail silently or exhaust retries without operator notice.
- **Latency Spikes:** Runaway durations and queue backlog growth degrade SLAs.
- **Root-Cause Obscurity:** Debugging stack traces across distributed worker processes is slow and error-prone.

**Background Job Tracker** turns opaque background tasks into observable, measurable, and auditable workflows.

---

## 💡 Core Architectural Principle

> **The customer application owns task execution.**
> **BJT owns telemetry ingestion, reliability analysis, incident detection, AI investigation, and alerting.**

BJT does **not** act as a task broker or execute customer code. Your worker fleet simply reports execution lifecycle signals asynchronously using our zero-overhead Python SDK.

---

## ⚡ Core Capabilities

- **Zero-Impact SDK Telemetry:** Microsecond non-blocking in-memory queueing, process-fork safety (Celery prefork), and resilient exponential backoff retry.
- **Automated Task Discovery:** Automatically discovers task names, queues, and worker hostnames on startup.
- **Real-Time Percentile Metrics:** Instant visibility into $p50$, $p90$, $p95$, and $p99$ execution durations, throughput, and error rates.
- **Automated Incident Detection:** Alerts trigger incidents when task failure rates, consecutive crashes, or duration SLAs cross thresholds.
- **AI Reliability Assistant:** Interactive incident investigation powered by grounded telemetry reasoning, stack trace analysis, evidence citation, and confidence estimation.
- **Team Incident Assignment & Runbooks:** Assign incidents to team members, track resolution lifecycles, and execute step-by-step mitigation runbooks.
- **Multi-Tenant Workspaces:** Secure team boundaries, granular role-based access control (`Owner`, `Admin`, `Member`), and hashed project API keys.
- **Multi-Channel Alerting:** Instant notifications via Email, HMAC-signed Webhooks, and In-App feeds.

---

## 🗺️ Documentation Navigation

| Section | Description |
|---|---|
| [**Installation**](getting-started/installation.md) | Step-by-step guide to run BJT backend and frontend locally using Docker Compose. |
| [**SDK Quickstart**](getting-started/sdk-quickstart.md) | 3-line drop-in setup for Celery (Django, FastAPI, Flask, Standalone) and Python RQ. |
| [**Platform & Dashboard Guide**](features/platform-guide.md) | Visual guide explaining all sidebar sections, reliability baselines, API keys, and admin tools. |
| [**AI Reliability Assistant**](features/ai-reliability-assistant.md) | Grounded incident investigation, traceback analysis, and recommendation generation. |
| [**Incident Management**](features/incident-management.md) | Incident triage, team assignment, mitigation runbooks, and postmortems. |
| [**Alerting & Notifications**](features/alerting-and-notifications.md) | Rule evaluation, policy configuration, and delivery channels (Email, Webhooks, In-App). |
| [**Architecture Overview**](architecture/overview.md) | System components, non-blocking telemetry pipeline, and queue processing architecture. |
| [**Domain Model**](architecture/domain-model.md) | Entities, relationships, and multi-tenant isolation patterns. |
| [**Testing & Quality**](development/testing.md) | Running backend pytest suites, SDK tests, and code formatting with Ruff. |
