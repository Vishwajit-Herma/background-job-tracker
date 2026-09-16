"use client";

import { useState } from "react";
import { Check, Copy, Terminal, ExternalLink, Package } from "lucide-react";
import { ScrollReveal } from "@/components/bjt/landing/scroll-reveal";

const codeSnippets = {
  celery: {
    title: "Django & Celery Integration",
    lang: "python",
    code: `import os
from celery import Celery
from background_job_tracker import Tracker
from background_job_tracker.integrations.celery import CeleryIntegration

# 1. Standard Celery application setup
app = Celery("my_project")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# 2. Initialize BJT Telemetry (Reads credentials from environment)
tracker = Tracker(
    api_key=os.getenv("BACKGROUND_JOB_TRACKER_API_KEY"),
    base_url=os.getenv("BACKGROUND_JOB_TRACKER_BASE_URL", "https://app.jobtracker.io"),
)

# 3. Attach CeleryIntegration - zero-config signal hooks for task lifecycle
CeleryIntegration(app=app, tracker=tracker)

@app.task
def process_monthly_invoice(customer_id: int):
    # Durations, retries, failures, and tracebacks are automatically tracked!
    return generate_invoice_pdf(customer_id)`,
  },
  fastapi: {
    title: "FastAPI Integration",
    lang: "python",
    code: `import os
from fastapi import FastAPI
from celery import Celery
from background_job_tracker import Tracker
from background_job_tracker.integrations.celery import CeleryIntegration

app = FastAPI(title="My Async API")

# 1. Configure Celery instance for FastAPI
celery_app = Celery("fastapi_worker", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))

# 2. Initialize BJT Tracker & Attach Integration
tracker = Tracker(
    api_key=os.getenv("BACKGROUND_JOB_TRACKER_API_KEY"),
    base_url=os.getenv("BACKGROUND_JOB_TRACKER_BASE_URL", "https://app.jobtracker.io"),
)
CeleryIntegration(app=celery_app, tracker=tracker)

# 3. Define worker task
@celery_app.task(name="tasks.sync_user_stripe_events")
def sync_user_stripe_events(user_id: int):
    # Execution metrics & failures automatically sent to BJT!
    return process_stripe_sync(user_id)`,
  },
  flask: {
    title: "Flask Integration",
    lang: "python",
    code: `import os
from flask import Flask
from celery import Celery, Task
from background_job_tracker import Tracker
from background_job_tracker.integrations.celery import CeleryIntegration

# 1. Initialize Flask Application & Config
app = Flask(__name__)
app.config.from_mapping(
    CELERY=dict(
        broker_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        result_backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    ),
)

# 2. Configure Celery with Flask App Context
def make_celery(flask_app):
    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(flask_app.name, task_cls=FlaskTask)
    celery_app.config_from_object(flask_app.config["CELERY"])
    return celery_app

celery_app = make_celery(app)

# 3. Attach BJT Telemetry Tracker
tracker = Tracker(api_key=os.getenv("BACKGROUND_JOB_TRACKER_API_KEY"))
CeleryIntegration(app=celery_app, tracker=tracker)

# 4. Define Flask background task
@celery_app.task
def send_user_welcome_email(user_id: int):
    # Executions & tracebacks automatically reported to BJT!
    return send_email(user_id)`,
  },
  rq: {
    title: "Python RQ (Redis Queue)",
    lang: "python",
    code: `import os
from redis import Redis
from rq import Worker, Queue
from background_job_tracker import Tracker
from background_job_tracker.integrations.rq import RQIntegration

# 1. Initialize Tracker & RQ Integration
tracker = Tracker(api_key=os.getenv("BACKGROUND_JOB_TRACKER_API_KEY"))
rq_integration = RQIntegration(tracker=tracker, modules=["my_app.tasks"])

# 2. Attach integration to worker script
if __name__ == "__main__":
    redis_conn = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    queue = Queue("default", connection=redis_conn)
    worker = Worker([queue], connection=redis_conn)

    rq_integration.attach(worker)
    worker.work()`,
  },
  custom: {
    title: "Manual / Custom Python Worker",
    lang: "python",
    code: `import os
from background_job_tracker import Tracker

# Initialize Tracker client
tracker = Tracker(
    api_key=os.getenv("BACKGROUND_JOB_TRACKER_API_KEY"),
    batch_size=50,
    flush_interval=2.0,
)

# Manually report background execution events
tracker.enqueue_event({
    "task_identifier": "reports.generate_monthly_pdf",
    "external_id": "job_984572049",
    "status": "success",  # "running" | "success" | "failure" | "retry"
    "duration_seconds": 2.45,
    "started_at": "2026-09-16T12:00:00.000Z",
    "completed_at": "2026-09-16T12:00:02.450Z",
    "worker": "worker-node-1",
    "queue": "reports",
})

# Ensure pending events are flushed on shutdown
tracker.shutdown(timeout=5.0)`,
  },
  rest: {
    title: "REST Telemetry API (Any Language)",
    lang: "bash",
    code: `# Ingest execution events from Node, Go, Rust, or Ruby
curl -X POST https://app.jobtracker.io/api/v1/executions/batch/ \\
  -H "X-API-Key: bjt_live_xxxxxxxxxxxxxxxx" \\
  -H "Content-Type: application/json" \\
  -d '{
    "executions": [
      {
        "task_identifier": "tasks.send_welcome_email",
        "external_id": "task-9a8b7c6d",
        "status": "success",
        "duration_seconds": 0.145,
        "queue": "emails",
        "worker": "worker-1@prod"
      }
    ]
  }'`,
  },
};

export function LandingCodeTabs() {
  const [activeTab, setActiveTab] = useState<keyof typeof codeSnippets>("celery");
  const [copied, setCopied] = useState(false);

  const current = codeSnippets[activeTab];

  const handleCopy = () => {
    navigator.clipboard.writeText(current.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section id="code-example" className="py-20 bg-background border-t border-border/60">
      <div className="container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <ScrollReveal>
          <div className="text-center max-w-3xl mx-auto mb-10">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-primary mb-2">
              Developer Integration
            </h2>
            <h3 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
              From Your Code To BJT In 3 Lines
            </h3>
            <p className="mt-4 text-base sm:text-lg text-muted-foreground">
              Zero-config Celery & RQ signal hooks, automatic task discovery, and lightweight async sender. Supports Django, FastAPI, Flask & custom Python workers.
            </p>

            {/* Quick Pip Install & PyPI Redirect */}
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <div className="inline-flex items-center gap-2 rounded-lg border border-border/80 bg-zinc-950 px-4 py-2 text-xs font-mono text-zinc-200 shadow-sm">
                <span className="text-emerald-400">$</span>
                <span>pip install background-job-tracker</span>
              </div>
              <a
                href="https://pypi.org/project/background-job-tracker/"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg border border-primary/30 bg-primary/10 px-3.5 py-2 text-xs font-medium text-primary hover:bg-primary/20 transition-colors shadow-xs"
              >
                <Package className="h-3.5 w-3.5" />
                <span>View on PyPI</span>
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </div>
        </ScrollReveal>

        {/* Code Container */}
        <ScrollReveal delayMs={150}>
          <div className="max-w-4xl mx-auto rounded-xl border border-border/80 bg-zinc-950 text-zinc-100 shadow-2xl overflow-hidden hover:border-primary/40 transition-colors">
          {/* Header Tabs */}
          <div className="flex flex-wrap items-center justify-between border-b border-zinc-800 bg-zinc-900/80 px-4 py-2.5 gap-2">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-zinc-700" />
              <span className="h-3 w-3 rounded-full bg-zinc-700" />
              <span className="h-3 w-3 rounded-full bg-zinc-700" />
              <div className="flex items-center gap-1.5 ml-3">
                <Terminal className="h-3.5 w-3.5 text-zinc-400" />
                <span className="text-xs font-mono text-zinc-400">{current.title}</span>
              </div>
            </div>

            {/* Tab Switch Buttons */}
            <div className="flex flex-wrap items-center gap-1 bg-zinc-950 p-1 rounded-md border border-zinc-800 text-xs">
              <button
                onClick={() => setActiveTab("celery")}
                className={`px-3 py-1 rounded font-medium transition-all ${
                  activeTab === "celery"
                    ? "bg-primary text-primary-foreground shadow-xs"
                    : "text-zinc-400 hover:text-zinc-100"
                }`}
              >
                Django
              </button>
              <button
                onClick={() => setActiveTab("fastapi")}
                className={`px-3 py-1 rounded font-medium transition-all ${
                  activeTab === "fastapi"
                    ? "bg-primary text-primary-foreground shadow-xs"
                    : "text-zinc-400 hover:text-zinc-100"
                }`}
              >
                FastAPI
              </button>
              <button
                onClick={() => setActiveTab("flask")}
                className={`px-3 py-1 rounded font-medium transition-all ${
                  activeTab === "flask"
                    ? "bg-primary text-primary-foreground shadow-xs"
                    : "text-zinc-400 hover:text-zinc-100"
                }`}
              >
                Flask
              </button>
              <button
                onClick={() => setActiveTab("rq")}
                className={`px-3 py-1 rounded font-medium transition-all ${
                  activeTab === "rq"
                    ? "bg-primary text-primary-foreground shadow-xs"
                    : "text-zinc-400 hover:text-zinc-100"
                }`}
              >
                Python RQ
              </button>
              <button
                onClick={() => setActiveTab("custom")}
                className={`px-3 py-1 rounded font-medium transition-all ${
                  activeTab === "custom"
                    ? "bg-primary text-primary-foreground shadow-xs"
                    : "text-zinc-400 hover:text-zinc-100"
                }`}
              >
                Custom Worker
              </button>
              <button
                onClick={() => setActiveTab("rest")}
                className={`px-3 py-1 rounded font-medium transition-all ${
                  activeTab === "rest"
                    ? "bg-primary text-primary-foreground shadow-xs"
                    : "text-zinc-400 hover:text-zinc-100"
                }`}
              >
                REST API
              </button>
            </div>
          </div>

          {/* Code Box with IDE Syntax Colors & Line Numbers */}
          <div className="relative p-5 overflow-x-auto bg-zinc-950 text-zinc-200">
            <button
              onClick={handleCopy}
              className="absolute top-4 right-4 z-10 flex items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-900 px-2.5 py-1 text-xs text-zinc-300 hover:bg-zinc-800 transition-colors shadow-sm"
            >
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                  <span className="text-emerald-400 font-medium">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  <span>Copy</span>
                </>
              )}
            </button>
            <HighlightedCode code={current.code} lang={current.lang} />
          </div>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}

{/* IDE Syntax Highlight Tokenizer */}
function HighlightedCode({ code, lang }: { code: string; lang: string }) {
  const lines = code.split("\n");

  return (
    <div className="font-mono text-xs sm:text-sm leading-relaxed table w-full border-collapse">
      {lines.map((line, idx) => {
        const lineNum = idx + 1;
        const trimmed = line.trim();

        // Full line comment
        if (trimmed.startsWith("#")) {
          return (
            <div key={idx} className="table-row">
              <span className="table-cell pr-4 text-right select-none text-zinc-600 text-xs w-8">{lineNum}</span>
              <span className="table-cell text-zinc-500 italic">{line}</span>
            </div>
          );
        }

        // Decorator (@app.task, @celery_app.task)
        if (trimmed.startsWith("@")) {
          return (
            <div key={idx} className="table-row">
              <span className="table-cell pr-4 text-right select-none text-zinc-600 text-xs w-8">{lineNum}</span>
              <span className="table-cell text-amber-300 font-medium">{line}</span>
            </div>
          );
        }

        return (
          <div key={idx} className="table-row">
            <span className="table-cell pr-4 text-right select-none text-zinc-600 text-xs w-8">{lineNum}</span>
            <span className="table-cell whitespace-pre">{highlightLineTokens(line, lang)}</span>
          </div>
        );
      })}
    </div>
  );
}

function highlightLineTokens(line: string, lang: string) {
  // Tokenizer pattern matching strings, keywords, classes, numbers, and comments
  const tokenRegex = /("[^"]*"|'[^']*'|#.*|\b(?:import|from|def|return|class|as|with|if|in|__name__|curl|pip|install|POST|export)\b|\b(?:Celery|Tracker|CeleryIntegration|RQIntegration|FastAPI|Flask|Worker|Queue|Redis|Task|FlaskTask)\b|\b\d+(?:\.\d+)?\b)/g;

  const parts = line.split(tokenRegex);

  return parts.map((part, i) => {
    if (!part) return null;

    // Strings (green)
    if ((part.startsWith('"') && part.endsWith('"')) || (part.startsWith("'") && part.endsWith("'"))) {
      return <span key={i} className="text-emerald-300">{part}</span>;
    }

    // Inline comments (gray italic)
    if (part.startsWith("#")) {
      return <span key={i} className="text-zinc-500 italic">{part}</span>;
    }

    // Python / Bash Keywords (purple)
    if (/^(import|from|def|return|class|as|with|if|in|__name__|curl|pip|install|POST|export)$/.test(part)) {
      return <span key={i} className="text-purple-400 font-semibold">{part}</span>;
    }

    // Builtin Classes & Framework Objects (sky blue)
    if (/^(Celery|Tracker|CeleryIntegration|RQIntegration|FastAPI|Flask|Worker|Queue|Redis|Task|FlaskTask)$/.test(part)) {
      return <span key={i} className="text-sky-300 font-semibold">{part}</span>;
    }

    // Numbers (amber orange)
    if (/^\d+(\.\d+)?$/.test(part)) {
      return <span key={i} className="text-amber-400">{part}</span>;
    }

    // CLI Flags (yellow)
    if (/^-[XHd]$/.test(part)) {
      return <span key={i} className="text-amber-300 font-semibold">{part}</span>;
    }

    return part;
  });
}

