import logging
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone

from apps.executions.models import Execution
from apps.incidents.models import Incident, IncidentIntelligence
from apps.reliability.models import ReliabilityFinding

logger = logging.getLogger(__name__)

ANALYSIS_VERSION = "1.0"
MINIMUM_SAMPLE_SIZE = 5
MAX_WINDOW_MINUTES = 60


def determine_analysis_window(incident, now=None):
    """
    Determines a deterministic analysis window for an incident.
    - For open/acknowledged incidents: window ends at `now`.
    - For resolved incidents: window ends at min(resolved_at, created_at + 60m).
    - Window starts at created_at - 15m, expanding to 30m, then 60m if sample count < 5.
    Never exceeds 60 minutes backwards.
    """
    if now is None:
        now = timezone.now()

    if incident.status == Incident.Status.RESOLVED and incident.resolved_at:
        max_resolved_end = incident.created_at + timedelta(minutes=MAX_WINDOW_MINUTES)
        window_end = min(incident.resolved_at, max_resolved_end)
        if window_end <= incident.created_at:
            window_end = incident.created_at + timedelta(minutes=1)
    else:
        window_end = max(now, incident.created_at + timedelta(seconds=1))

    # Determine window start with deterministic step-wise expansion: 15m -> 30m -> 60m
    project_id = incident.project_id
    job_id = incident.job_id

    candidate_minutes = [15, 30, 60]
    selected_minutes = 15

    for mins in candidate_minutes:
        cand_start = incident.created_at - timedelta(minutes=mins)
        qs = Execution.objects.filter(
            job__project_id=project_id,
            job__is_deleted=False,
            created_at__gte=cand_start,
            created_at__lte=window_end,
        )
        if job_id:
            qs = qs.filter(job_id=job_id)

        count = qs.count()
        selected_minutes = mins
        if count >= MINIMUM_SAMPLE_SIZE:
            break

    window_start = incident.created_at - timedelta(minutes=selected_minutes)
    return window_start, window_end, selected_minutes


def calculate_incident_impact(incident, window_start, window_end, window_minutes, executions=None):
    """
    Calculates impact metrics across the incident window and compares with baseline.
    Accepts pre-loaded executions to avoid duplicate DB query execution.
    """
    project_id = incident.project_id

    if executions is None:
        executions = list(
            Execution.objects.filter(
                job__project_id=project_id,
                job__is_deleted=False,
                created_at__gte=window_start,
                created_at__lte=window_end,
            ).select_related("job")
        )

    total_executions = len(executions)
    failures_count = sum(1 for e in executions if e.status == Execution.Status.FAILED)
    retries_count = sum(1 for e in executions if e.status == Execution.Status.RETRY)
    successes_count = sum(1 for e in executions if e.status == Execution.Status.SUCCESS)

    failure_rate = (
        round((failures_count / total_executions) * 100, 2) if total_executions > 0 else 0.0
    )
    retry_rate = round((retries_count / total_executions) * 100, 2) if total_executions > 0 else 0.0

    # Group by job
    job_stats = {}
    for e in executions:
        jid = e.job_id
        if jid not in job_stats:
            job_stats[jid] = {
                "id": jid,
                "name": e.job.name,
                "task_identifier": e.job.task_identifier,
                "total": 0,
                "failures": 0,
                "retries": 0,
            }
        job_stats[jid]["total"] += 1
        if e.status == Execution.Status.FAILED:
            job_stats[jid]["failures"] += 1
        elif e.status == Execution.Status.RETRY:
            job_stats[jid]["retries"] += 1

    affected_jobs = sorted(
        job_stats.values(),
        key=lambda x: (x["failures"], x["retries"], x["total"]),
        reverse=True,
    )

    # Workers & Queues
    workers = {e.worker for e in executions if e.worker}
    queues = {e.queue for e in executions if e.queue}

    # Incident duration calculation
    incident_end = incident.resolved_at or timezone.now()
    incident_duration_seconds = max(0, int((incident_end - incident.created_at).total_seconds()))

    # Baseline comparison for job-level incidents
    baseline_comparisons = {}
    if incident.job and hasattr(incident.job, "baseline"):
        baseline = getattr(incident.job, "baseline", None)
        if baseline and baseline.is_sufficient:
            base_fr = baseline.failure_rate if baseline.failure_rate is not None else 0.0
            base_rr = baseline.retry_rate if baseline.retry_rate is not None else 0.0
            base_p95 = baseline.p95_runtime_ms

            # Calculate job-specific failure rate in window
            job_execs = [e for e in executions if e.job_id == incident.job_id]
            job_total = len(job_execs)
            job_failures = sum(1 for e in job_execs if e.status == Execution.Status.FAILED)
            job_retries = sum(1 for e in job_execs if e.status == Execution.Status.RETRY)

            job_fr = round((job_failures / job_total) * 100, 2) if job_total > 0 else 0.0
            job_rr = round((job_retries / job_total) * 100, 2) if job_total > 0 else 0.0

            # Strict multiplier semantics: only return multiplier when current > baseline
            fr_multiplier = round(job_fr / base_fr, 2) if base_fr > 0 and job_fr > base_fr else None
            rr_multiplier = round(job_rr / base_rr, 2) if base_rr > 0 and job_rr > base_rr else None

            baseline_comparisons = {
                "baseline_failure_rate": round(base_fr, 2),
                "current_failure_rate": job_fr,
                "failure_rate_multiplier": fr_multiplier,
                "baseline_retry_rate": round(base_rr, 2),
                "current_retry_rate": job_rr,
                "retry_rate_multiplier": rr_multiplier,
                "baseline_p95_ms": round(base_p95, 2) if base_p95 else None,
            }

    return {
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "window_minutes": window_minutes,
        "incident_duration_seconds": incident_duration_seconds,
        "affected_jobs_count": len(affected_jobs),
        "affected_jobs": affected_jobs,
        "affected_executions_count": total_executions,
        "failures_count": failures_count,
        "retries_count": retries_count,
        "successes_count": successes_count,
        "failure_rate": failure_rate,
        "retry_rate": retry_rate,
        "affected_workers_count": len(workers),
        "affected_workers": sorted(workers),
        "affected_queues_count": len(queues),
        "affected_queues": sorted(queues),
        "baseline_comparisons": baseline_comparisons,
    }


def find_correlated_signals(incident, window_start, window_end, executions):
    """
    Deterministically identifies related signals within the same project.
    Strictly isolated to incident.project_id and requires true temporal overlap:
    - Findings detected_at <= window_end AND (recovered_at IS NULL OR recovered_at >= window_start)
    - Incidents created_at <= window_end AND (resolved_at IS NULL OR resolved_at >= window_start)
    Deduplicates duplicate signals.
    """
    project_id = incident.project_id
    raw_correlations = []

    # 1. Related Reliability / Anomaly Findings in Project with true temporal overlap
    findings = (
        ReliabilityFinding.objects.filter(
            job__project_id=project_id,
            detected_at__lte=window_end,
        )
        .filter(Q(recovered_at__isnull=True) | Q(recovered_at__gte=window_start))
        .select_related("job")
    )
    for finding in findings:
        reasons = [
            f"Active reliability finding: {finding.condition_type}",
            "Detected within incident timeframe",
            "Same project",
        ]
        if incident.job_id and finding.job_id == incident.job_id:
            reasons.append("Same job")

        # Map queues associated with this finding's job
        job_queues = sorted({e.queue for e in executions if e.job_id == finding.job_id and e.queue})
        if not job_queues:
            # Check historical executions for queue association if not present in window
            job_queues = list(
                Execution.objects.filter(job_id=finding.job_id)
                .exclude(queue="")
                .values_list("queue", flat=True)
                .distinct()[:5]
            )

        raw_correlations.append(
            {
                "target_type": "FINDING",
                "target_id": finding.id,
                "target_name": f"{finding.job.name} - {finding.get_condition_type_display()}",
                "condition_type": finding.condition_type,
                "job_id": finding.job_id,
                "associated_queues": job_queues,
                "reasons": reasons,
                "correlation_strength": "STRONG"
                if finding.job_id == incident.job_id
                else "MODERATE",
            }
        )

    # 2. Same Worker Correlation
    worker_failure_jobs = {}
    for e in executions:
        if e.worker and e.status in [Execution.Status.FAILED, Execution.Status.RETRY]:
            worker_failure_jobs.setdefault(e.worker, set()).add(e.job.name)

    for worker, job_names in worker_failure_jobs.items():
        if len(job_names) > 1 or (incident.job and incident.job.name in job_names):
            raw_correlations.append(
                {
                    "target_type": "WORKER",
                    "target_id": None,
                    "target_name": worker,
                    "reasons": [
                        f"Worker '{worker}' experienced failures across {len(job_names)} job(s)",
                        "Shared worker execution node",
                        "Same project",
                    ],
                    "correlation_strength": "STRONG" if len(job_names) > 1 else "MODERATE",
                }
            )

    # 3. Same Queue Correlation
    queue_failure_jobs = {}
    for e in executions:
        if e.queue and e.status in [Execution.Status.FAILED, Execution.Status.RETRY]:
            queue_failure_jobs.setdefault(e.queue, set()).add(e.job.name)

    for queue, job_names in queue_failure_jobs.items():
        if len(job_names) > 1:
            raw_correlations.append(
                {
                    "target_type": "QUEUE",
                    "target_id": None,
                    "target_name": queue,
                    "reasons": [
                        f"Queue '{queue}' experienced failure cascades across {len(job_names)} jobs",
                        "Shared task queue",
                        "Same project",
                    ],
                    "correlation_strength": "MODERATE",
                }
            )

    # 4. Overlapping Incidents in Project with true temporal overlap
    overlapping_incidents = (
        Incident.objects.filter(
            project_id=project_id,
            created_at__lte=window_end,
        )
        .exclude(id=incident.id)
        .filter(Q(resolved_at__isnull=True) | Q(resolved_at__gte=window_start))
        .select_related("job", "alert_rule")
    )
    for other_inc in overlapping_incidents:
        reasons = [
            "Concurrent active incident",
            "Overlapping incident window",
            "Same project",
        ]
        if incident.job_id and other_inc.job_id == incident.job_id:
            reasons.append("Same job")

        rule_name = other_inc.alert_rule.metric if other_inc.alert_rule else "Rule"
        raw_correlations.append(
            {
                "target_type": "INCIDENT",
                "target_id": other_inc.id,
                "target_name": f"Incident #{other_inc.id} ({rule_name})",
                "reasons": reasons,
                "correlation_strength": "STRONG"
                if other_inc.job_id == incident.job_id
                else "MODERATE",
            }
        )

    # Deduplicate signals targeting the exact same entity
    deduped_correlations = []
    seen_keys = set()
    for c in raw_correlations:
        key = (c["target_type"], c["target_id"], c["target_name"])
        if key in seen_keys:
            existing = next(
                ec
                for ec in deduped_correlations
                if (ec["target_type"], ec["target_id"], ec["target_name"]) == key
            )
            for r in c["reasons"]:
                if r not in existing["reasons"]:
                    existing["reasons"].append(r)
        else:
            seen_keys.add(key)
            c["reasons"] = list(dict.fromkeys(c["reasons"]))
            deduped_correlations.append(c)

    return deduped_correlations


def identify_probable_causes(incident, impact, correlations, executions):
    """
    Ranks multiple probable root causes based on deterministic evidence.
    Candidates: WORKER, QUEUE, JOB, ANOMALY, INSUFFICIENT_EVIDENCE.
    Confidence: HIGH, MEDIUM, LOW, INSUFFICIENT_EVIDENCE.
    """
    candidates = []
    total_executions = impact["affected_executions_count"]
    failures_count = impact["failures_count"]
    failure_rate = impact["failure_rate"]

    # If insufficient data
    if total_executions < MINIMUM_SAMPLE_SIZE or (failures_count == 0 and not correlations):
        return [
            {
                "candidate": "INSUFFICIENT_EVIDENCE",
                "value": "INSUFFICIENT_DATA",
                "confidence": "INSUFFICIENT_EVIDENCE",
                "evidence": [
                    f"Sample size ({total_executions} execution(s)) in the {impact['window_minutes']}m analysis window is below the minimum required for root-cause inference.",
                    "No conclusive telemetry patterns detected.",
                ],
            }
        ]

    # 1. Check Worker Degradation
    # Count failures and executions per worker
    worker_stats = {}
    for e in executions:
        w = e.worker or "unassigned"
        if w not in worker_stats:
            worker_stats[w] = {"total": 0, "failures": 0}
        worker_stats[w]["total"] += 1
        if e.status == Execution.Status.FAILED:
            worker_stats[w]["failures"] += 1

    if failures_count >= 3:
        for worker, stats in worker_stats.items():
            if worker != "unassigned" and stats["failures"] >= 3:
                fail_ratio = stats["failures"] / failures_count
                other_execs = total_executions - stats["total"]
                other_failures = failures_count - stats["failures"]
                other_rate = (
                    round((other_failures / other_execs) * 100, 1) if other_execs > 0 else 0.0
                )

                # High confidence requires >= 5 total executions, >= 3 failures, and >= 70% concentration
                if fail_ratio >= 0.70 and total_executions >= MINIMUM_SAMPLE_SIZE:
                    evidence = [
                        f"{round(fail_ratio * 100)}% of affected failures occurred on worker '{worker}' ({stats['failures']}/{failures_count}).",
                    ]
                    if other_execs > 0:
                        evidence.append(
                            f"Other worker nodes operated with a {other_rate}% failure rate ({other_failures}/{other_execs} executions)."
                        )
                    else:
                        evidence.append(
                            "All executions in the analysis window ran solely on this worker node."
                        )

                    candidates.append(
                        {
                            "candidate": "WORKER",
                            "value": worker,
                            "confidence": "HIGH",
                            "evidence": evidence,
                        }
                    )
                elif fail_ratio >= 0.50:
                    candidates.append(
                        {
                            "candidate": "WORKER",
                            "value": worker,
                            "confidence": "MEDIUM",
                            "evidence": [
                                f"{round(fail_ratio * 100)}% of affected failures concentrated on worker '{worker}' ({stats['failures']}/{failures_count}).",
                            ],
                        }
                    )

    # 2. Check Queue Congestion / Overdue Delays
    # Scoped strictly per queue to avoid cross-queue false positive association
    pending_by_queue = {}
    for e in executions:
        if e.status == Execution.Status.PENDING and e.queue:
            pending_by_queue[e.queue] = pending_by_queue.get(e.queue, 0) + 1

    all_candidate_queues = set(pending_by_queue.keys())
    for c in correlations:
        if (
            c.get("target_type") == "FINDING"
            and "OVERDUE" in c.get("condition_type", c.get("target_name", "")).upper()
        ):
            for q in c.get("associated_queues", []):
                all_candidate_queues.add(q)

    for queue in sorted(all_candidate_queues):
        p_count = pending_by_queue.get(queue, 0)
        queue_overdue = [
            c
            for c in correlations
            if c.get("target_type") == "FINDING"
            and "OVERDUE" in c.get("condition_type", c.get("target_name", "")).upper()
            and queue in c.get("associated_queues", [])
        ]

        if p_count >= 3 or queue_overdue:
            evidence = []
            if p_count > 0:
                evidence.append(
                    f"Queue '{queue}' accumulated {p_count} pending/unprocessed execution(s) during the incident window."
                )
            if queue_overdue:
                evidence.append(
                    f"Active OVERDUE_EXECUTION finding recorded for job running on queue '{queue}'."
                )

            confidence = (
                "HIGH"
                if (queue_overdue and p_count >= 3)
                else ("MEDIUM" if p_count >= 3 or queue_overdue else "LOW")
            )
            candidates.append(
                {
                    "candidate": "QUEUE",
                    "value": queue,
                    "confidence": confidence,
                    "evidence": evidence,
                }
            )

    # 3. Check Anomaly Finding Evidence
    anomaly_correlations = [
        c
        for c in correlations
        if c["target_type"] == "FINDING"
        and any(
            t in c.get("condition_type", c["target_name"]).upper()
            or any(t in r.upper() for r in c["reasons"])
            for t in ["ANOMALY", "FAILURE_RATE", "RETRY_RATE", "DURATION"]
        )
    ]
    for ac in anomaly_correlations:
        candidates.append(
            {
                "candidate": "ANOMALY",
                "value": ac["target_name"],
                "confidence": "HIGH" if ac.get("correlation_strength") == "STRONG" else "MEDIUM",
                "evidence": [
                    f"Statistical reliability anomaly detected: {ac['target_name']}.",
                    *ac["reasons"],
                ],
            }
        )

    # 4. Check Job-Level Failure Spike (if failures distributed across workers)
    has_worker_candidate = any(c["candidate"] == "WORKER" for c in candidates)
    if not has_worker_candidate and failures_count >= 3:
        target_job_name = incident.job.name if incident.job else "Project jobs"
        base_fr = impact.get("baseline_comparisons", {}).get("baseline_failure_rate")
        evidence = [
            f"Failures occurred across multiple workers without concentration on a single host ({len(worker_stats)} worker(s) involved).",
            f"Failure rate rose to {failure_rate}% across {total_executions} executions.",
        ]
        if base_fr:
            multiplier = impact.get("baseline_comparisons", {}).get("failure_rate_multiplier")
            if multiplier:
                evidence.append(
                    f"Failure rate is {multiplier}x higher than the historical baseline ({base_fr}%)."
                )

        candidates.append(
            {
                "candidate": "JOB",
                "value": target_job_name,
                "confidence": "HIGH" if failure_rate >= 50.0 else "MEDIUM",
                "evidence": evidence,
            }
        )

    # If no candidate was found despite some failures
    if not candidates:
        candidates.append(
            {
                "candidate": "INSUFFICIENT_EVIDENCE",
                "value": "INDETERMINATE",
                "confidence": "LOW",
                "evidence": [
                    f"Observed {failures_count} failure(s) across {total_executions} execution(s), but no definitive pattern (worker, queue, or anomaly) exceeded the diagnostic threshold.",
                ],
            }
        )

    # Sort candidates by confidence: HIGH > MEDIUM > LOW > INSUFFICIENT_EVIDENCE
    confidence_order = {"HIGH": 4, "MEDIUM": 3, "LOW": 2, "INSUFFICIENT_EVIDENCE": 1}
    candidates.sort(key=lambda c: confidence_order.get(c["confidence"], 0), reverse=True)

    return candidates


def compute_incident_intelligence(incident, now=None):
    """
    Runs the full deterministic Incident Intelligence calculation for an incident.
    Returns a dictionary of derived intelligence fields using a single execution queryset.
    """
    if now is None:
        now = timezone.now()

    window_start, window_end, window_minutes = determine_analysis_window(incident, now=now)

    # Load executions ONCE for impact, correlations, and probable cause analysis
    executions = list(
        Execution.objects.filter(
            job__project_id=incident.project_id,
            job__is_deleted=False,
            created_at__gte=window_start,
            created_at__lte=window_end,
        ).select_related("job")
    )

    impact = calculate_incident_impact(
        incident=incident,
        window_start=window_start,
        window_end=window_end,
        window_minutes=window_minutes,
        executions=executions,
    )

    correlations = find_correlated_signals(
        incident=incident,
        window_start=window_start,
        window_end=window_end,
        executions=executions,
    )

    probable_causes = identify_probable_causes(
        incident=incident,
        impact=impact,
        correlations=correlations,
        executions=executions,
    )

    return {
        "impact": impact,
        "correlations": correlations,
        "probable_causes": probable_causes,
        "analysis_window_start": window_start,
        "analysis_window_end": window_end,
        "analysis_version": ANALYSIS_VERSION,
    }


def compute_and_save_incident_intelligence(incident_id):
    """
    Loads incident, computes intelligence, and updates or creates IncidentIntelligence row.
    Guards against race conditions where a slower, older calculation finishes after a newer one.
    """
    try:
        incident = Incident.objects.select_related("project", "job").get(id=incident_id)
    except Incident.DoesNotExist:
        logger.warning("Cannot compute intelligence: Incident %s does not exist.", incident_id)
        return None

    calc_started_at = timezone.now()
    data = compute_incident_intelligence(incident, now=calc_started_at)

    # Check if an existing newer calculation already exists
    existing = IncidentIntelligence.objects.filter(incident=incident).first()
    if existing:
        # If existing record has a newer analysis_window_end or was calculated after our start, preserve it
        if (
            existing.analysis_window_end
            and data["analysis_window_end"] < existing.analysis_window_end
        ):
            logger.info(
                "Skipping intelligence save for Incident %s: existing data is newer (%s > %s).",
                incident_id,
                existing.analysis_window_end,
                data["analysis_window_end"],
            )
            return existing

        if (
            existing.calculated_at
            and calc_started_at < existing.calculated_at
            and data["analysis_window_end"] <= existing.analysis_window_end
        ):
            logger.info(
                "Skipping intelligence save for Incident %s: existing record was calculated more recently (%s > %s).",
                incident_id,
                existing.calculated_at,
                calc_started_at,
            )
            return existing

    intelligence, _ = IncidentIntelligence.objects.update_or_create(
        incident=incident,
        defaults={
            "impact": data["impact"],
            "correlations": data["correlations"],
            "probable_causes": data["probable_causes"],
            "analysis_window_start": data["analysis_window_start"],
            "analysis_window_end": data["analysis_window_end"],
            "analysis_version": data["analysis_version"],
        },
    )
    return intelligence
