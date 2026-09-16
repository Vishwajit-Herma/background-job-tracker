# SDK Quickstart

The official Python SDK (`background-job-tracker`) provides drop-in telemetry integration for Celery, Python RQ, and custom worker scripts.

[![PyPI Version](https://img.shields.io/pypi/v/background-job-tracker?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/background-job-tracker/)

---

## 📦 Installation

Install from PyPI using your favorite package manager:

```bash
# Base package
pip install background-job-tracker

# Or with framework extras
pip install "background-job-tracker[celery]"
pip install "background-job-tracker[rq]"
pip install "background-job-tracker[all]"
```

Using `uv`:
```bash
uv add background-job-tracker
```

Using `poetry`:
```bash
poetry add background-job-tracker
```

---

## 🔑 1. Obtain Your Project API Key

1. Log in to your BJT Dashboard at [https://background-job-tracker-wine.vercel.app](https://background-job-tracker-wine.vercel.app/) (or `http://localhost:3000` locally).
2. Create or select your **Project**.
3. Navigate to **API Keys** and generate a new API key (e.g., `bjt_live_...`).
4. Set your environment variables:

```bash
export BACKGROUND_JOB_TRACKER_API_KEY="bjt_live_xxxxxxxxxxxxxxxx"
export BACKGROUND_JOB_TRACKER_BASE_URL="http://localhost:8000"  # or https://your-bjt-api.example.com
```

---

## ⚡ 2. Celery Integration (Django, FastAPI, Flask, Standalone)

Integrate with Celery in 3 lines of code inside your `celery.py`:

```python
import os
from celery import Celery
from background_job_tracker import Tracker
from background_job_tracker.integrations.celery import CeleryIntegration

# Standard Celery application setup
app = Celery("my_project")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Initialize BJT Tracker
tracker = Tracker()  # Automatically reads BACKGROUND_JOB_TRACKER_API_KEY and BACKGROUND_JOB_TRACKER_BASE_URL
CeleryIntegration(app=app, tracker=tracker)
```

### What Happens Automatically:
- **Task Discovery:** Automatically syncs registered tasks and signature queues with BJT on `worker_ready`.
- **Execution Telemetry:** Listens to `task_prerun`, `task_postrun`, `task_success`, `task_failure`, `task_retry`, and `task_revoked` signals.
- **Traceback Capture:** Automatically captures formatted exception tracebacks and error messages on task failure.

---

## 🔴 3. Python RQ (Redis Queue) Integration

Attach `RQIntegration` to your Python RQ worker script:

```python
import os
from redis import Redis
from rq import Worker, Queue
from background_job_tracker import Tracker
from background_job_tracker.integrations.rq import RQIntegration

# Initialize Tracker
tracker = Tracker(
    api_key=os.environ["BACKGROUND_JOB_TRACKER_API_KEY"],
    base_url=os.getenv("BACKGROUND_JOB_TRACKER_BASE_URL", "http://localhost:8000"),
)

# Configure RQ integration with your task modules
rq_integration = RQIntegration(
    tracker=tracker,
    modules=["my_app.tasks"],
)

if __name__ == "__main__":
    redis_conn = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    queue = Queue("default", connection=redis_conn)

    worker = Worker([queue], connection=redis_conn)
    rq_integration.attach(worker)

    worker.work(with_scheduler=True)
```

---

## 🎯 4. Manual / Custom Task Telemetry

If you have standalone background threads or custom task loops, you can emit telemetry events directly:

```python
from background_job_tracker import Tracker

tracker = Tracker(api_key="bjt_live_xxxxxxxxxxxxxxxx")

# Enqueue an execution event
tracker.enqueue_event({
    "task_identifier": "reports.generate_monthly_pdf",
    "external_id": "job_984572049",
    "status": "success",  # "running" | "success" | "failure" | "retry" | "revoked"
    "duration_seconds": 2.45,
    "started_at": "2026-09-16T12:00:00.000000Z",
    "completed_at": "2026-09-16T12:00:02.450000Z",
    "worker": "worker-node-1",
    "queue": "reports",
    "retry_count": 0,
    "metadata": {
        "report_id": 402,
        "format": "pdf",
    },
})

# Flush on process shutdown
tracker.shutdown(timeout=5.0)
```

---

## ⚙️ Configuration Reference

| Option | Environment Variable | Default | Description |
|---|---|---|---|
| `api_key` | `BACKGROUND_JOB_TRACKER_API_KEY` | *Required* | Project API key. |
| `base_url` | `BACKGROUND_JOB_TRACKER_BASE_URL` | `http://localhost:8000` | Ingestion API base URL. |
| `batch_size` | `batch_size` | `100` | Max batch size before flushing to API. |
| `flush_interval` | `flush_interval` | `5.0` | Max interval (seconds) before flushing. |
| `max_queue_size`| `max_queue_size` | `10000` | In-memory queue limit for safe drop under disconnection. |
