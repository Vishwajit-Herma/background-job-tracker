# Platform & Dashboard Guide

Welcome to the **Background Job Tracker (BJT)** platform guide! This document explains every section and subsection of the BJT web dashboard, what each feature is used for, and how they work together to ensure maximum reliability for your background workers.

---

## 🧭 Navigation Overview

The BJT sidebar is divided into core operational sections and administrative configuration:

```text
+----------------------------------------+----------------------------------------+
|                             Team Workspace (Tenant)                             |
+----------------------------------------+----------------------------------------+
                                         |
           +-----------------------------+-----------------------------+
           |                             |                             |
           v                             v                             v
+---------------------+       +---------------------+       +---------------------+
|      PROJECTS       |       |        JOBS         |       |     EXECUTIONS      |
|---------------------|       |---------------------|       |---------------------|
| - API Keys          |       | - Reliability       |       | - Live Stream       |
| - Settings          |       | - Baselines         |       | - Sanitized Errors  |
| - Health Score      |       | - Expectations      |       | - Tracebacks        |
+---------------------+       +---------------------+       +---------------------+
           |                             |                             |
           +-----------------------------+-----------------------------+
           |                             |                             |
           v                             v                             v
+---------------------+       +---------------------+       +---------------------+
|      ANALYTICS      |       |       ALERTS        |       |      INCIDENTS      |
|---------------------|       |---------------------|       |---------------------|
| - Latency (P50/P95) |       | - SLA Thresholds    |       | - AI Investigation  |
| - Throughput Rate   |       | - Anomaly Alerts    |       | - Runbook Actions   |
| - Queue Metrics     |       | - Retry Failures    |       | - Postmortems       |
+---------------------+       +---------------------+       +---------------------+
           |                             |                             |
           +-----------------------------+-----------------------------+
                                         |
                  +----------------------+----------------------+
                  |                                             |
                  v                                             v
+-----------------------------------+         +-----------------------------------+
|       TEAM & USER SETTINGS        |         |       ADMIN: NOTIFICATIONS        |
|-----------------------------------|         |-----------------------------------|
| - Roles (Owner, Admin, Member)    |         | - Channels (Email, Webhooks)      |
| - Profile, Gravatar & Avatar      |         | - Severity & Event Routing Rules  |
+-----------------------------------+         +-----------------------------------+
```

---

## 1. 📁 Projects

**Projects** represent individual applications, services, or environments (e.g. `Production Billing Service`, `Staging Web`, `Data Pipeline`).

### Key Capabilities & Subsections:
- **Project Switcher & Context:** Filter your entire dashboard view to a single project or view all projects across your organization.
- **API Keys (`BJT_API_KEY`):** Secure, cryptographically hashed ingestion tokens used by the Python SDK (`tracker.init()`) to transmit telemetry.
  - Create multiple keys per project with custom names (e.g. `Production Celery Worker`, `Staging RQ Worker`).
  - Raw secret keys are displayed only once upon creation; only SHA-256 hashes are stored in the database.
  - Safely revoke old or compromised keys with zero application downtime.
- **Project Settings:** Configure project name, slug, description, and status (`Active` or `Archived`).
- **Health Summary:** High-level project KPIs including total registered jobs, active executions, error rates, and project-level health score.

---

## 2. 📋 Jobs

**Jobs** represent unique background tasks or asynchronous functions monitored by the platform (e.g. `billing.process_invoice`, `emails.send_welcome`, `reports.generate_pdf`).

```
Jobs > [Job Name]
├── Overview (Status, Failure Rate, Execution Count, Last Run Status)
├── Reliability (Execution Expectations, Statistical Baselines, Health Status, MTTR/MTBF)
├── Analytics (P50/P95/P99 Durations, Volume, Error Distribution)
└── Executions (Filtered list of individual runs for this task)
```

### Key Subsections:

### A. Reliability Tab
The Reliability tab tracks the health, cadence, and baseline performance of your background task:
- **Execution Expectations:**
  - **Expected Interval:** The expected cadence between scheduled runs (e.g. *Every 6 hours*, *Every 15 minutes*).
  - **Grace Period:** A buffer window (e.g. 5 minutes) before flagging a scheduled run as missed.
  - **Maximum Runtime:** The execution duration threshold after which a running task is flagged as stalled/hung.
  - **Maximum Queue Delay:** The maximum acceptable time a task can wait in the broker before a worker picks it up.
- **Expectation Source Badge:**
  - `✨ Based on baseline`: BJT automatically analyzed recent execution history (median interval) and derived the schedule without requiring manual setup.
  - `Configured`: Explicitly set and customized by an engineer via the **Edit** dialog.
- **Reliability Metrics:**
  - **MTTR (Mean Time to Resolve):** Velocity at which incidents for this job are resolved.
  - **MTBF (Mean Time Between Failures):** Frequency interval between failure incidents.
  - **Current Status:** `Normal`, `Missed`, `Stalled`, or `Degraded`.

### B. Statistical Baselines
BJT runs periodic baseline calculations over a 7-day rolling execution window:
- Computes $p50$, $p90$, $p95$, and $p99$ runtimes strictly from successfully completed executions.
- Establishes baseline failure rates, retry rates, and average hourly execution volume.

### C. Job Analytics & Executions Tabs
- Task-specific time-series charts showing duration percentiles and error rates.
- Complete execution history filtered exclusively to this task.

---

## 3. ⚡ Executions

**Executions** is the live telemetry feed showing every single run of every background task across your worker fleet.

### Key Capabilities & Subsections:
- **Live Real-Time Stream:** Live updates via WebSockets as tasks transition between `STARTED`, `SUCCESS`, `FAILED`, `RETRY`, and `REVOKED`.
- **Advanced Filtering:** Filter by Project, Job Name, Status, Queue, Worker Hostname, or Date Range.
- **Execution Details Drawer / Page:**
  - **Timing & Latency:** Queue arrival time, worker start time, duration in milliseconds ($ms$), and finish timestamp.
  - **Worker Context:** Worker hostname, process PID, and target queue name.
  - **Retry Lifecycle:** Current retry attempt number and retry error context.
  - **Sanitized Traceback:** Full Python exception traceback with automated secret/credential redaction.
  - **Custom Metadata:** Any custom key-value payload attached via the SDK (e.g. `order_id`, `batch_size`).

---

## 4. 📈 Analytics

**Analytics** provides aggregated, high-level metrics across projects, queues, and worker infrastructure.

### Key Subsections:
- **Throughput & Volume:** Total execution volume over time (1h, 24h, 7d, 30d) with interactive time-window selection.
- **Failure & Retry Rates:** Proportional breakdown of successful vs. failed vs. retried executions.
- **Duration Percentiles ($p50, p90, p95, p99$):** Identifies long-tail latency spikes and sluggish jobs.
- **Worker Fleet & Queue Distribution:** Displays load distribution across worker instances and identifies congested queues.

---

## 5. 🔔 Alerts

**Alerts** allow you to define rule-based thresholds that monitor worker behavior and trigger incidents when SLAs are breached.

### Key Capabilities & Subsections:
- **Alert Rules:** Configure rules based on key reliability signals:
  - **Failure Rate:** Trigger if failure rate exceeds $X\%$ over a time window.
  - **Retry Rate:** Trigger if retried tasks exceed $X\%$ over a time window.
  - **P95 Duration SLA:** Trigger if execution duration exceeds expected threshold in milliseconds.
  - **Missed Execution:** Trigger if a scheduled job misses its expected cadence and grace period.
  - **Stalled Execution:** Trigger if a running task exceeds its maximum runtime limit.
  - **Overdue Execution:** Trigger if a task waits in queue longer than acceptable delay.
  - **Anomaly Alerts:** Statistical anomalies for failure rate, retry rate, duration, or volume compared to learned baselines.
- **Scoping:** Apply rules globally across an entire project or bind them to high-priority critical jobs.
- **Severity Levels:** `CRITICAL` or `DEGRADED`.

---

## 6. ⚠️ Incidents, Runbooks & Postmortems

The incident response system consists of three interconnected capabilities:

### A. Incidents
- **Automated Lifecycle:**
  - Created automatically when an Alert Rule threshold is breached.
  - Auto-resolves automatically when worker telemetry returns to healthy levels.
- **Incident Status & Triage:** Track state (`OPEN`, `ACKNOWLEDGED`, `RESOLVED`) and assign incidents to team members.
- **AI Reliability Assistant (Powered by Gemini):**
  - Click **"Investigate with AI"** on any incident.
  - The AI inspects failed executions, stack traces, correlated worker degradation, and error patterns to produce **Probable Root Cause**, **Evidence Citations**, **Impact Radius**, and **Actionable Recommendations**.
- **Incident Intelligence:** Automatically classifies whether an issue is a **Job Code Error**, **Queue Congestion**, or **Worker Host Degradation**.
- **Audit Timeline & Team Notes:** Complete audit trail of state transitions, actors, and human investigation notes.

### B. Runbooks
**Runbooks** are standardized, step-by-step operational playbooks that guide engineers through incident mitigation and recovery.
- **Interactive Action Checklists:** Markdown-formatted guides with operational commands, checks, and mitigation steps.
- **Trigger Association:** Attach runbooks to specific jobs or trigger types (e.g. `MISSED_EXECUTION`, `FAILURE_RATE`, `STALLED_EXECUTION`) so they automatically surface during an incident.
- **Runbook Executions:** Track step-by-step progress, completion times, and execution history during an active outage.

### C. Incident Postmortems & Action Items
**Postmortems** provide a structured framework for blameless post-incident analysis and continuous learning.
- **Postmortem Document:**
  - **Status:** `Pending`, `In Review`, or `Completed`.
  - **Core Analysis:** Summary, Impact Summary, Probable Cause, Confirmed Root Cause, and Resolution details.
  - **Contributing Factors:** Structured list of underlying factors that led to the outage.
  - **Curated Timeline:** Key milestone events during the incident and response.
  - **Retrospective:** Document *What went well* and *What went wrong*.
  - **Review Workflow:** Assigned reviewer and formal review completion timestamp.
- **Postmortem Action Items:**
  - Track preventative action items derived from the postmortem.
  - Assign ownership to specific team members with due dates and completion states (`Pending`, `In Progress`, `Completed`, `Cancelled`).

---

## 7. 👥 Team

**Team** manages workspace multi-tenancy, user access, and collaboration.

### Key Capabilities & Subsections:
- **Member Directory:** List all team members with their email, avatar, and assigned role.
- **Role-Based Access Control (RBAC):**
  - **`Owner`:** Complete control including billing, team deletion, and ownership transfer.
  - **`Admin`:** Can create/delete projects, manage API keys, invite members, and configure notification policies.
  - **`Member`:** Can view telemetry, investigate incidents, manage jobs, execute runbooks, and edit expectations.
- **Invitations Tab:** Send email invitations with secure token expiration.
- **Team Settings:** Rename workspace, manage team slugs, or switch between multiple teams.

---

## 8. ⚙️ Settings

**Settings** manages personal user account settings and profile information.

### Key Capabilities & Subsections:
- **Personal Profile:** Update your first name and last name.
- **Avatar System:** Gravatar integration with fallback name initials and deterministic background colors per user to prevent duplicate avatars.
- **Locked Email Identity:** Email address is locked to your authenticated login credentials to prevent unauthorized account changes.

---

## 9. 🛡️ ADMIN (Notification Configuration)

The **Admin** section is visible to team administrators for managing communication and alert routing.

### A. 💬 Notification Channels
Define the delivery destinations for alert events:
- **Email Channels:** Send alerts directly to developer mailboxes or team distribution lists.
- **Webhook Channels:** Deliver secure HMAC-signed JSON payloads to external systems, Slack, Discord, or PagerDuty.
- **In-App Notifications:** Real-time in-app notification bell in the top navigation bar.

### B. 🛡️ Notification Policies
Define routing rules that connect project channels to incident events:
- **Severity Matching:** Route notifications based on incident severity (`CRITICAL` vs. `DEGRADED`).
- **Event Filtering:** Select which incident events trigger notifications (e.g. `Created`, `Assigned`, `Acknowledged`, `Note Added`, `Resolved`, `Reopened`).

---

## 🚀 Recommended Workflow for New Users

1. **Create a Project** in [**Projects**](#1-projects) and copy your **Project API Key**.
2. **Install the SDK** in your worker application (`pip install background-job-tracker`) and add `tracker.init()`.
3. **Start your workers** — your jobs will automatically appear in [**Jobs**](#2-jobs).
4. **Inspect real-time runs** in [**Executions**](#3-executions) as tasks execute.
5. **Set up an Alert Rule** in [**Alerts**](#5-alerts) and a [**Notification Channel**](#9-admin-notification-configuration).
6. **Let BJT learn your baselines** — after a few runs, BJT will automatically monitor your schedules and durations!
