from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import F
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.config_management.responses import CustomResponseMixin
from apps.config_management.views import BaseViewSetConfig, CustomBaseGenericViewSet
from apps.executions.models import Execution
from apps.jobs.models import Job
from apps.projects.models import Project
from apps.reliability.models import JobExpectation, ReliabilityFinding
from apps.reliability.permissions import ReliabilityPermission
from apps.reliability.serializers import (
    BaselineRecalculateQuerySerializer,
    JobBaselineSerializer,
    JobExpectationSerializer,
    JobReliabilityOverviewSerializer,
    ProjectReliabilityOverviewSerializer,
    ReliabilityFindingSerializer,
)
from apps.reliability.services import (
    get_job_reliability_overview,
)
from apps.reliability.tasks import recalculate_single_job_baseline


class ReliabilityFindingViewSet(
    BaseViewSetConfig, CustomResponseMixin, viewsets.ReadOnlyModelViewSet
):
    """
    API endpoint to list and view reliability findings (Missed, Stalled, Overdue).
    Enforces team tenant isolation.
    """

    serializer_class = ReliabilityFindingSerializer
    permission_classes = [permissions.IsAuthenticated, ReliabilityPermission]

    def get_queryset(self):
        user = self.request.user
        qs = (
            ReliabilityFinding.objects.select_related(
                "job", "job__project", "execution", "incident"
            )
            .filter(
                job__is_deleted=False,
                job__project__is_deleted=False,
                job__project__team__members__user=user,
                job__project__team__members__is_active=True,
            )
            .order_by("-detected_at")
        )

        job_id = self.request.query_params.get("job_id")
        if job_id:
            qs = qs.filter(job_id=job_id)

        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(job__project_id=project_id)

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        condition_type = self.request.query_params.get("condition_type")
        if condition_type:
            qs = qs.filter(condition_type=condition_type)

        return qs.distinct()


class JobReliabilityViewSet(CustomBaseGenericViewSet):
    """
    API endpoint for viewing and configuring job reliability monitoring.
    Provides single-job overview and expectation updates.
    """

    permission_classes = [permissions.IsAuthenticated, ReliabilityPermission]

    @extend_schema(
        responses={200: JobReliabilityOverviewSerializer},
    )
    def retrieve(self, request, pk=None):
        """
        Returns full reliability metrics and findings for a single job.
        """
        job = get_object_or_404(
            Job.objects.select_related("project", "project__team", "expectation", "baseline"),
            id=pk,
            is_deleted=False,
            project__is_deleted=False,
        )
        self.check_object_permissions(request, job)

        data = get_job_reliability_overview(job)
        serializer = JobReliabilityOverviewSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(responses={200: JobExpectationSerializer})
    @action(detail=True, methods=["get", "put", "patch"], url_path="expectation")
    def expectation(self, request, pk=None):
        """
        Retrieve or update the execution expectations for a job.
        GET never creates a database row.
        PUT/PATCH creates or updates the database row when necessary.
        """
        job = get_object_or_404(
            Job.objects.select_related("project", "project__team"),
            id=pk,
            is_deleted=False,
            project__is_deleted=False,
        )
        self.check_object_permissions(request, job)

        if request.method in ["PUT", "PATCH"]:
            expectation, _ = JobExpectation.objects.get_or_create(job=job)
            serializer = JobExpectationSerializer(
                expectation, data=request.data, partial=(request.method == "PATCH")
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        expectation = getattr(job, "expectation", None)
        if expectation:
            serializer = JobExpectationSerializer(expectation)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Return default expectation shape without creating a database row
        return Response(
            {
                "id": None,
                "job": job.id,
                "expected_interval_seconds": None,
                "max_runtime_seconds": None,
                "grace_period_seconds": 0,
                "max_queue_delay_seconds": None,
                "is_enabled": True,
                "created_at": None,
                "updated_at": None,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=BaselineRecalculateQuerySerializer,
        responses={202: JobBaselineSerializer},
    )
    @action(detail=True, methods=["post"], url_path="recalculate-baseline")
    def recalculate_baseline(self, request, pk=None):
        """
        Queues an asynchronous baseline recalculation for a job.
        """
        job = get_object_or_404(
            Job.objects.select_related("project", "project__team"),
            id=pk,
            is_deleted=False,
            project__is_deleted=False,
        )
        self.check_object_permissions(request, job)

        serializer = BaselineRecalculateQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sample_window = serializer.validated_data.get("sample_window_days", 7)

        recalculate_single_job_baseline.delay(job.id, sample_window_days=sample_window)

        return Response(
            {
                "status": "accepted",
                "message": f"Baseline recalculation queued for job {job.id} over a {sample_window}-day window.",
                "job_id": job.id,
                "sample_window_days": sample_window,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ProjectReliabilityViewSet(CustomBaseGenericViewSet):
    """
    API endpoint for viewing reliability summaries across all jobs in a project.
    Uses bulk distinct queries to avoid N+1 query overhead and excessive row loading.
    """

    permission_classes = [permissions.IsAuthenticated, ReliabilityPermission]

    @extend_schema(
        responses={200: ProjectReliabilityOverviewSerializer},
    )
    def retrieve(self, request, pk=None):
        """
        Returns a rollup of reliability states across all jobs for a project.
        """
        project = get_object_or_404(
            Project.objects.select_related("team"),
            id=pk,
            is_deleted=False,
        )
        self.check_object_permissions(request, project)

        now = timezone.now()
        jobs = list(
            Job.objects.filter(
                project=project,
                status="active",
                is_deleted=False,
            ).select_related("expectation", "baseline")
        )

        job_ids = [j.id for j in jobs]

        # Fetch ONLY the single latest execution per job directly from DB (1 row per job)
        latest_executions = (
            Execution.objects.filter(job_id__in=job_ids)
            .order_by("job_id", F("started_at").desc(nulls_last=True), "-created_at")
            .distinct("job_id")
            .only("id", "job_id", "started_at", "created_at")
        )
        latest_exec_by_job = {e.job_id: e for e in latest_executions}

        # Bulk fetch active findings in 1 query
        active_findings = ReliabilityFinding.objects.filter(
            job_id__in=job_ids,
            status=ReliabilityFinding.Status.ACTIVE,
        )
        active_findings_by_job = {}
        for f in active_findings:
            active_findings_by_job.setdefault(f.job_id, []).append(f)

        job_summaries = []
        healthy_count = 0
        missed_count = 0
        stalled_count = 0
        overdue_count = 0
        anomalous_count = 0
        total_active_findings = 0

        anomaly_condition_types = {
            ReliabilityFinding.ConditionType.FAILURE_RATE_ANOMALY,
            ReliabilityFinding.ConditionType.RETRY_RATE_ANOMALY,
            ReliabilityFinding.ConditionType.DURATION_ANOMALY,
            ReliabilityFinding.ConditionType.EXECUTION_VOLUME_ANOMALY,
        }

        for job in jobs:
            expectation = getattr(job, "expectation", None)
            baseline = getattr(job, "baseline", None)
            latest_exec = latest_exec_by_job.get(job.id)
            findings = active_findings_by_job.get(job.id, [])

            expected_interval = None
            expectation_source = "NONE"
            if expectation and expectation.expected_interval_seconds:
                expected_interval = expectation.expected_interval_seconds
                expectation_source = "CONFIGURED"
            elif baseline and baseline.is_sufficient and baseline.median_interval_seconds:
                expected_interval = int(baseline.median_interval_seconds)
                expectation_source = "BASELINE"

            max_runtime = None
            if expectation and expectation.max_runtime_seconds:
                max_runtime = expectation.max_runtime_seconds
            elif baseline and baseline.is_sufficient and baseline.p95_runtime_ms:
                max_runtime = int(max(1, round(baseline.p95_runtime_ms / 1000 * 1.5)))

            last_execution_at = None
            next_expected_at = None
            missed_after_at = None

            if latest_exec:
                occurrence_time = latest_exec.started_at or latest_exec.created_at
                last_execution_at = occurrence_time.isoformat() if occurrence_time else None
                if expected_interval and occurrence_time:
                    next_expected = occurrence_time + timedelta(seconds=expected_interval)
                    grace = expectation.grace_period_seconds if expectation else 0
                    missed_after = next_expected + timedelta(seconds=grace)
                    next_expected_at = next_expected.isoformat()
                    missed_after_at = missed_after.isoformat()

            # Determine state with strict precedence:
            # DISABLED > STALLED > OVERDUE > MISSED > ANOMALOUS > HEALTHY
            finding_types = {f.condition_type for f in findings}
            if expectation and not expectation.is_enabled:
                state = "DISABLED"
            elif ReliabilityFinding.ConditionType.STALLED_EXECUTION in finding_types:
                state = "STALLED"
                stalled_count += 1
            elif ReliabilityFinding.ConditionType.OVERDUE_EXECUTION in finding_types:
                state = "OVERDUE"
                overdue_count += 1
            elif ReliabilityFinding.ConditionType.MISSED_EXECUTION in finding_types:
                state = "MISSED"
                missed_count += 1
            elif finding_types & anomaly_condition_types:
                state = "ANOMALOUS"
                anomalous_count += 1
            else:
                state = "HEALTHY"
                healthy_count += 1

            # Only populate overdue_by_seconds if MISSED state is active
            overdue_by = 0
            if state == "MISSED" and missed_after_at and now > missed_after:
                overdue_by = int((now - missed_after).total_seconds())

            active_count = len(findings)
            total_active_findings += active_count

            job_summaries.append(
                {
                    "job_id": job.id,
                    "job_name": job.name,
                    "task_identifier": job.task_identifier,
                    "current_state": state,
                    "expectation_source": expectation_source,
                    "expected_interval_seconds": expected_interval,
                    "max_runtime_seconds": max_runtime,
                    "last_execution_at": last_execution_at,
                    "next_expected_at": next_expected_at,
                    "missed_after_at": missed_after_at,
                    "overdue_by_seconds": overdue_by,
                    "active_findings_count": active_count,
                }
            )

        data = {
            "project_id": project.id,
            "project_name": project.name,
            "total_jobs": len(job_summaries),
            "healthy_jobs_count": healthy_count,
            "missed_jobs_count": missed_count,
            "stalled_jobs_count": stalled_count,
            "overdue_jobs_count": overdue_count,
            "anomalous_jobs_count": anomalous_count,
            "active_findings_count": total_active_findings,
            "jobs": job_summaries,
        }

        serializer = ProjectReliabilityOverviewSerializer(data)
        return Response(serializer.data)
