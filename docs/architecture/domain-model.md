# Domain Model

Background Job Tracker is organized around a hierarchical multi-tenant domain structure.

---

## 🗺️ Entity Relationship Hierarchy

```text
Team (Organization)
 └── Project (Application / Environment)
      ├── APIKey (Authentication & Scoping)
      ├── NotificationChannel (Email, Webhook, In-App)
      ├── AlertRule (Evaluation Policies)
      └── Job (Background Task Signature)
           ├── Execution (Task Lifecycle Events & Tracebacks)
           └── Incident (Reliability Issues)
                ├── IncidentEvent (Timeline Audit Events)
                ├── Runbook (Mitigation Playbooks)
                └── Postmortem (Resolution & Preventive Actions)
```

---

## 🏛️ Core Domain Models

### 1. `Team` & `TeamMember` (`apps/teams`)
- **`Team`**: Represents an organization or customer account.
- **`TeamMember`**: Binds a `User` to a `Team` with role-based permissions (`Owner`, `Admin`, `Member`).

### 2. `Project` & `APIKey` (`apps/projects`)
- **`Project`**: Logical application or deployment environment (e.g. `billing-service-prod`).
- **`APIKey`**: Hashed project-scoped credential used by the Python SDK to ingest execution telemetry.

### 3. `Job` (`apps/jobs`)
- Represents a distinct background task signature (e.g. `reports.tasks.generate_pdf`).
- Computes real-time health score, success rates, and duration percentiles ($p50, p90, p95, p99$).

### 4. `Execution` (`apps/executions`)
- Represents an individual run of a `Job`.
- Stores status (`success`, `failure`, `retry`, `revoked`), duration, queue wait latency, worker hostname, and exception tracebacks.

### 5. `Incident` (`apps/incidents`)
- Created when an `AlertRule` is breached.
- Tracks severity (`DEGRADED`, `CRITICAL`), status (`OPEN`, `ACKNOWLEDGED`, `RESOLVED`), and assigned responder (`TeamMember`).
- Contains interactive `Runbook` executions and `Postmortem` records.
