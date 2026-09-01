"""Service layer for AI Reliability Assistant."""

import json
import logging
import re
from typing import Any

from django.db.models import Q
from django.utils import timezone

from apps.ai.providers.base import AIProvider, AIValidationError
from apps.ai.providers.gemini import GeminiProvider
from apps.ai.serializers import AIInvestigationResponseSerializer
from apps.executions.models import Execution
from apps.incidents.intelligence import determine_analysis_window
from apps.incidents.models import Incident, Runbook
from apps.incidents.services import build_incident_knowledge

logger = logging.getLogger(__name__)

# Maximum bytes for a single traceback sent to Gemini
_TRACEBACK_MAX_BYTES = 10_240  # ~10 KB

# System instruction strictly enforcing grounding, evidence, and safety rules
AI_INVESTIGATION_SYSTEM_INSTRUCTION = """
You are the Background Job Reliability Assistant for BJT (Background Job Tracker).

Your goal is to investigate background-job incidents using ONLY the BJT telemetry and domain context provided to you. Give concise, technically useful, evidence-backed explanations and recommended investigation/remediation steps.

CRITICAL RULES:

1. GROUNDING
   - Use ONLY the supplied BJT context.
   - Never invent executions, logs, metrics, infrastructure state, stack frames, or events.
   - If the context does not contain enough evidence, say so.

2. EVIDENCE LEVELS
   Clearly distinguish:
   - OBSERVED: directly present in BJT telemetry.
   - INFERRED / PROBABLE: conclusion supported by multiple observed signals.
   - CONFIRMED: explicitly documented as the confirmed root cause in the postmortem.
   Never convert a probable cause into a confirmed root cause.

3. TRACEBACK / EXECUTION ANALYSIS
   When representative_failed_executions contains error_type, error_message, or traceback:
   - Treat them as observed execution evidence.
   - Identify the immediate exception and the relevant application frame when visible.
   - Explain what the exception means based only on the supplied traceback/error.
   - Connect the execution error with worker, queue, reliability, anomaly, and incident-intelligence evidence when available.
   - A traceback identifies what failed; it does NOT by itself prove the broader root cause.
   - Do not invent missing source-code behavior.

4. ROOT-CAUSE REASONING
   Prefer this order:
   a. Observed execution error / traceback
   b. Correlated telemetry
   c. Phase 9 probable cause
   d. Phase 10 confirmed root cause, if documented
   When these disagree, explicitly explain the difference.

5. RECOMMENDATIONS
   Provide practical next investigation/remediation steps for a human operator.
   Recommendations must be based on supplied evidence.
   Prefer existing BJT runbooks when relevant.
   Do NOT perform, simulate, or claim to have performed remediation.
   Do NOT recommend actions that contradict the current BJT state.
   Example: do not recommend editing a COMPLETED postmortem or executing an inactive runbook.

6. HISTORICAL INCIDENTS
   Historical incidents are supporting evidence only.
   Do not assume a previous incident has the same root cause as the current incident.
   State clearly when a historical incident is only similar rather than confirmed to be the same cause.

7. EVIDENCE ATTRIBUTION
   Every important claim should be supported by evidence.
   Use only these source categories:
   - incident
   - incident_event
   - analytics
   - reliability
   - incident_intelligence
   - runbook
   - postmortem
   - execution

8. UNCERTAINTY
   If evidence is incomplete, conflicting, or insufficient:
   - say what is known,
   - say what is uncertain,
   - avoid guessing,
   - use confidence = INSUFFICIENT_EVIDENCE when appropriate.

9. ANSWER QUALITY
   For investigation questions:
   - answer the question first,
   - explain the strongest evidence,
   - distinguish immediate error from broader cause,
   - provide concise next actions.

10. SAFETY
   Never expose or reproduce secrets, credentials, API keys, tokens, passwords, or other sensitive values even if they appear in supplied context.
"""


def find_similar_incidents(incident: Incident, limit: int = 3) -> list[dict[str, Any]]:
    """Find historical incidents within the same project for context matching."""
    base_qs = (
        Incident.objects.filter(project_id=incident.project_id)
        .exclude(id=incident.id)
        .select_related("postmortem", "job")
        .order_by("-created_at")
    )

    # Prioritize incidents matching the same job or trigger metric
    metric_type = (incident.trigger_metadata or {}).get("metric_type")
    if incident.job_id and metric_type:
        query_filter = Q(job_id=incident.job_id) | Q(trigger_metadata__metric_type=metric_type)
    elif incident.job_id:
        query_filter = Q(job_id=incident.job_id)
    elif metric_type:
        query_filter = Q(trigger_metadata__metric_type=metric_type)
    else:
        query_filter = Q()

    matches = list(base_qs.filter(query_filter)[:limit]) if query_filter else list(base_qs[:limit])

    results = []
    for inc in matches:
        confirmed_rc = None
        postmortem_summary = None
        if hasattr(inc, "postmortem") and inc.postmortem:
            confirmed_rc = inc.postmortem.confirmed_root_cause or None
            postmortem_summary = inc.postmortem.summary or None

        results.append(
            {
                "id": inc.id,
                "incident_ref": f"INC-{inc.id}",
                "severity": inc.severity,
                "status": inc.status,
                "job_name": inc.job.name if inc.job else None,
                "trigger_metric": (inc.trigger_metadata or {}).get("metric_type"),
                "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
                "resolution_type": inc.resolution_type,
                "confirmed_root_cause": confirmed_rc,
                "postmortem_summary": postmortem_summary,
            }
        )
    return results


ALLOWED_METADATA_KEYS = {
    "metric_type",
    "metric_value",
    "threshold",
    "threshold_value",
    "window",
    "window_minutes",
    "timestamps",
    "timestamp",
    "condition",
    "finding_type",
    "status",
    "count",
    "duration",
    "rate",
    "actual_value",
    "expected_value",
    "baseline_value",
    "evaluated_at",
    "resolved_by_name",
    "reopened_by_name",
    "runbook_name",
}


def _sanitize_metadata(metadata: Any) -> Any:
    """Filter metadata using telemetry key allowlisting and redact sensitive secret-like fields."""
    if isinstance(metadata, dict):
        sanitized = {}
        for k, v in metadata.items():
            k_lower = str(k).lower()
            if any(
                s in k_lower
                for s in ["token", "secret", "password", "key", "auth", "credential", "bearer"]
            ):
                sanitized[k] = "[REDACTED]"
            elif k_lower in ALLOWED_METADATA_KEYS:
                sanitized[k] = _sanitize_metadata(v)
            else:
                # Omit or sanitize non-allowlisted metadata fields
                sanitized[k] = _sanitize_metadata(v)
        return sanitized
    if isinstance(metadata, list):
        return [_sanitize_metadata(item) for item in metadata]
    return metadata


# Regex for credential-bearing URLs: https://user:pass@host or http://token@host
_CREDENTIAL_URL_RE = re.compile(
    r"https?://[^@\s>]+:[^@\s>]+@[^\s>]+",
    re.IGNORECASE,
)

# Patterns within traceback text that indicate credential leakage
_TRACEBACK_SECRET_PATTERNS = re.compile(
    r"(?i)(token|secret|password|passwd|api_key|apikey|bearer|credential)\s*[=:\s]+\s*[\'\"]?[\w\-\.]{8,}[\'\"]?"
)


def _sanitize_traceback(traceback: str) -> str:
    """Sanitize a traceback string for safe transmission to an AI provider.

    - Redacts credential-bearing URLs.
    - Redacts secret-like variable assignments.
    - Truncates to _TRACEBACK_MAX_BYTES, preserving the final (most relevant) frames.
    """
    if not traceback:
        return ""

    # 1. Redact credential-bearing URLs
    sanitized = _CREDENTIAL_URL_RE.sub("[REDACTED_URL]", traceback)

    # 2. Redact inline secret assignments (e.g. token='abc123', password=xyz)
    sanitized = _TRACEBACK_SECRET_PATTERNS.sub(
        lambda m: m.group(0).split(m.group(1))[0] + m.group(1) + "=[REDACTED]",
        sanitized,
    )

    # 3. Bound to ~10 KB — preserve the tail (most recent frames, exception line)
    encoded = sanitized.encode("utf-8", errors="replace")
    if len(encoded) > _TRACEBACK_MAX_BYTES:
        truncated = encoded[-_TRACEBACK_MAX_BYTES:].decode("utf-8", errors="replace")
        sanitized = "[...truncated...]\n" + truncated

    return sanitized


def _error_signature(error_type: str, error_message: str) -> str:
    """Produce a short deduplication key for an error."""
    # Use error_type + first 120 chars of error_message as the signature
    return f"{error_type}::{(error_message or '')[:120]}"


def get_representative_failed_executions(
    incident: Incident,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return up to `limit` representative failed executions for an incident.

    Strategy:
    1. Query failed Execution rows for the job attached to the incident,
       within the incident's analysis window.
    2. Prefer distinct error signatures to maximise diagnostic value.
    3. Fall back to the most recent failed executions if the job has no
       analysis-window hits.
    4. Sanitize tracebacks before returning.
    """
    if not incident.job_id:
        return []

    window_start, window_end, _ = determine_analysis_window(incident, now=timezone.now())

    # Candidates within the analysis window, most recent first
    window_qs = (
        Execution.objects.filter(
            job_id=incident.job_id,
            status=Execution.Status.FAILED,
            created_at__gte=window_start,
            created_at__lte=window_end,
        )
        .only(
            "id",
            "external_id",
            "error_type",
            "error_message",
            "traceback",
            "worker",
            "queue",
            "started_at",
            "finished_at",
        )
        .order_by("-created_at")
    )

    # Deduplicate by error signature, collect up to `limit` distinct ones
    seen_signatures: set[str] = set()
    selected: list[Execution] = []

    for exc in window_qs.iterator():
        sig = _error_signature(exc.error_type, exc.error_message)
        if sig not in seen_signatures:
            seen_signatures.add(sig)
            selected.append(exc)
        if len(selected) >= limit:
            break

    # If the analysis window produced no hits, fall back to the most recent
    # failed executions for this job regardless of time
    if not selected:
        fallback_qs = (
            Execution.objects.filter(
                job_id=incident.job_id,
                status=Execution.Status.FAILED,
            )
            .only(
                "id",
                "external_id",
                "error_type",
                "error_message",
                "traceback",
                "worker",
                "queue",
                "started_at",
                "finished_at",
            )
            .order_by("-created_at")[:limit]
        )
        for exc in fallback_qs:
            sig = _error_signature(exc.error_type, exc.error_message)
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                selected.append(exc)

    return [
        {
            "execution_id": exc.id,
            "external_id": exc.external_id,
            "error_type": exc.error_type or None,
            "error_message": exc.error_message or None,
            "traceback": _sanitize_traceback(exc.traceback),
            "worker": exc.worker or None,
            "queue": exc.queue or None,
            "started_at": exc.started_at.isoformat() if exc.started_at else None,
            "occurred_at": exc.finished_at.isoformat() if exc.finished_at else None,
        }
        for exc in selected
    ]


def build_ai_context(incident: Incident, question: str | None = None) -> dict[str, Any]:
    """Construct a bounded, compact, and sanitized context artifact for AI investigation."""
    knowledge = build_incident_knowledge(incident)

    # 1. Sanitize Core Incident
    inc_data = knowledge.get("incident") or {}
    sanitized_incident = {
        "id": inc_data.get("id"),
        "reference": f"INC-{inc_data.get('id')}",
        "status": inc_data.get("status"),
        "severity": inc_data.get("severity"),
        "assigned_to": inc_data.get("assigned_to_name"),
        "created_at": inc_data.get("created_at"),
        "resolved_at": inc_data.get("resolved_at"),
        "resolution_type": inc_data.get("resolution_type"),
        "trigger_metadata": _sanitize_metadata(inc_data.get("trigger_metadata") or {}),
    }

    # 2. Bounded Timeline Events (Limit to latest 15 events)
    raw_events = knowledge.get("events") or []
    sanitized_events = [
        {
            "id": evt.get("id"),
            "event_type": evt.get("event_type"),
            "event_time": evt.get("event_time"),
            "actor": evt.get("actor_name") or "System",
            "metadata": _sanitize_metadata(evt.get("metadata") or {}),
        }
        for evt in raw_events[-15:]
    ]

    # 3. Intelligence (Probable causes, correlations, impact)
    intelligence = knowledge.get("intelligence") or {}

    # 4. Runbook Executions
    runbook_execs = [
        {
            "id": rx.get("id"),
            "runbook_id": rx.get("runbook"),
            "runbook_name": rx.get("runbook_name"),
            "status": rx.get("status"),
            "started_at": rx.get("started_at"),
            "completed_at": rx.get("completed_at"),
        }
        for rx in (knowledge.get("runbook_executions") or [])
    ]

    # 5. Postmortem
    postmortem = knowledge.get("postmortem")

    # 6. Historical Similar Incidents (max 3, project-scoped)
    similar_incidents = find_similar_incidents(incident, limit=3)

    # 7. Available Active Runbooks for Project / Job
    available_runbooks_qs = Runbook.objects.filter(
        project_id=incident.project_id,
        is_active=True,
    ).filter(Q(job__isnull=True) | Q(job_id=incident.job_id))[:5]

    available_runbooks = [
        {
            "id": rb.id,
            "name": rb.name,
            "description": rb.description,
            "trigger_type": rb.trigger_type,
            "steps_count": len(rb.steps) if isinstance(rb.steps, list) else 0,
        }
        for rb in available_runbooks_qs
    ]

    # 8. Representative failed executions with sanitized tracebacks
    failed_executions = get_representative_failed_executions(incident, limit=3)

    return {
        "incident": sanitized_incident,
        "timeline_events": sanitized_events,
        "intelligence": intelligence,
        "runbook_executions": runbook_execs,
        "postmortem": postmortem,
        "similar_historical_incidents": similar_incidents,
        "available_runbooks": available_runbooks,
        "representative_failed_executions": failed_executions,
    }


def investigate_incident(
    incident: Incident,
    question: str,
    provider: AIProvider | None = None,
) -> dict[str, Any]:
    """Execute context-grounded AI investigation for an incident."""
    if provider is None:
        provider = GeminiProvider()

    context = build_ai_context(incident, question=question)

    prompt = (
        "BJT Incident Context:\n"
        f"```json\n{json.dumps(context, separators=(',', ':'))}\n```\n\n"
        f"User Query:\n{question}\n\n"
        "Provide a grounded, structured answer adhering strictly to schema requirements."
    )

    raw_response = provider.generate_json(
        prompt=prompt,
        system_instruction=AI_INVESTIGATION_SYSTEM_INSTRUCTION,
    )

    serializer = AIInvestigationResponseSerializer(data=raw_response)
    if not serializer.is_valid():
        logger.warning(
            "AI response schema validation failed for INC-%s: %s",
            incident.id,
            serializer.errors,
        )
        raise AIValidationError(f"Invalid AI response structure: {serializer.errors}")

    return serializer.validated_data
