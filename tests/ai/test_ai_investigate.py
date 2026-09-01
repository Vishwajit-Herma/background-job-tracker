"""Tests for Phase 11 AI Reliability Assistant (V1)."""

from unittest.mock import patch
from django.urls import reverse
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.ai.providers.base import (
    AIConfigurationError,
    AIProviderError,
    AIProviderTimeoutError,
)
from apps.ai.services import build_ai_context, find_similar_incidents
from apps.incidents.models import Incident, IncidentPostmortem
from apps.projects.models import Project
from apps.teams.models import Team, TeamMember
from apps.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user1(db):
    return User.objects.create(email="user1@example.com", password="password")


@pytest.fixture
def user2(db):
    return User.objects.create(email="user2@example.com", password="password")


@pytest.fixture
def team1(user1):
    team = Team.objects.create(name="Team 1", slug="team-1", owner=user1)
    return team


@pytest.fixture
def team2(user2):
    team = Team.objects.create(name="Team 2", slug="team-2", owner=user2)
    return team


@pytest.fixture
def project1(team1):
    return Project.objects.create(team=team1, name="Project 1")


@pytest.fixture
def project2(team2):
    return Project.objects.create(team=team2, name="Project 2")


@pytest.fixture
def incident1(project1):
    return Incident.objects.create(
        project=project1,
        severity=Incident.Severity.CRITICAL,
        status=Incident.Status.OPEN,
        trigger_metadata={
            "metric_type": "FAILURE_RATE",
            "metric_value": 0.85,
            "api_token": "secret_123",
        },
    )


@pytest.fixture
def incident2(project2):
    return Incident.objects.create(
        project=project2,
        severity=Incident.Severity.DEGRADED,
        status=Incident.Status.OPEN,
        trigger_metadata={"metric_type": "DURATION_ANOMALY"},
    )


MOCK_AI_RESPONSE = {
    "answer": "The incident occurred due to high failure rate spikes observed in telemetry.",
    "confidence": "HIGH",
    "evidence": [
        {
            "source": "incident",
            "reference_id": "INC-1",
            "fact": "Failure rate exceeded 85% at trigger time.",
        },
        {
            "source": "incident_intelligence",
            "reference_id": "INTEL-1",
            "fact": "Identified database connection exhaustion as probable cause.",
        },
    ],
    "recommendations": [
        {
            "action": "Check database connection pool utilization.",
            "reason": "Probable cause indicates database exhaustion.",
        }
    ],
}


@pytest.mark.django_db
class TestAIInvestigateAPI:
    """Test suite for AI investigation endpoint."""

    @patch("apps.ai.services.GeminiProvider.generate_json", return_value=MOCK_AI_RESPONSE)
    def test_authorized_incident_investigation_succeeds(
        self, mock_gemini, api_client, user1, incident1
    ):
        api_client.force_authenticate(user=user1)
        url = reverse("api:ai:incident-ai-investigate", args=[incident1.id])
        response = api_client.post(
            url, {"question": "Why did this incident happen?"}, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        raw = response.json()
        data = raw.get("data", raw)
        assert data["confidence"] == "HIGH"
        assert len(data["evidence"]) == 2
        assert data["evidence"][0]["source"] == "incident"
        assert len(data["recommendations"]) == 1
        mock_gemini.assert_called_once()

    @patch("apps.ai.services.GeminiProvider.generate_json", return_value=MOCK_AI_RESPONSE)
    def test_summarize_incident_prompt(self, mock_gemini, api_client, user1, incident1):
        api_client.force_authenticate(user=user1)
        url = reverse("api:ai:incident-ai-investigate", args=[incident1.id])
        response = api_client.post(url, {"question": "Summarize this incident"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        raw = response.json()
        data = raw.get("data", raw)
        assert "answer" in data
        assert isinstance(data["evidence"], list)

    def test_unauthenticated_access_rejected(self, api_client, incident1):
        url = reverse("api:ai:incident-ai-investigate", args=[incident1.id])
        response = api_client.post(url, {"question": "Why did this happen?"}, format="json")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_cross_project_tenant_access_rejected(self, api_client, user1, incident2):
        api_client.force_authenticate(user=user1)
        url = reverse("api:ai:incident-ai-investigate", args=[incident2.id])
        response = api_client.post(url, {"question": "Why did this happen?"}, format="json")
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

    def test_inactive_teammember_access_rejected(
        self, api_client, user1, team1, project1, incident1
    ):
        member = TeamMember.objects.get(team=team1, user=user1)
        member.is_active = False
        member.save()

        api_client.force_authenticate(user=user1)
        url = reverse("api:ai:incident-ai-investigate", args=[incident1.id])
        response = api_client.post(url, {"question": "Why did this happen?"}, format="json")
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

    def test_invalid_request_payload_returns_400(self, api_client, user1, incident1):
        api_client.force_authenticate(user=user1)
        url = reverse("api:ai:incident-ai-investigate", args=[incident1.id])
        response = api_client.post(url, {"question": ""}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch(
        "apps.ai.services.GeminiProvider.generate_json",
        side_effect=AIProviderError("Upstream service unavailable"),
    )
    def test_provider_failure_handled(self, mock_gemini, api_client, user1, incident1):
        api_client.force_authenticate(user=user1)
        url = reverse("api:ai:incident-ai-investigate", args=[incident1.id])
        response = api_client.post(url, {"question": "Why did this happen?"}, format="json")

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        data = response.json()
        assert (
            data.get("error_code") == "AI_PROVIDER_ERROR"
            or data.get("errors", {}).get("code") == "AI_PROVIDER_ERROR"
        )

    @patch(
        "apps.ai.services.GeminiProvider.generate_json",
        side_effect=AIProviderTimeoutError("Gemini timed out"),
    )
    def test_provider_timeout_handled(self, mock_gemini, api_client, user1, incident1):
        api_client.force_authenticate(user=user1)
        url = reverse("api:ai:incident-ai-investigate", args=[incident1.id])
        response = api_client.post(url, {"question": "Why did this happen?"}, format="json")

        assert response.status_code == status.HTTP_504_GATEWAY_TIMEOUT
        data = response.json()
        assert (
            data.get("error_code") == "AI_PROVIDER_TIMEOUT"
            or data.get("errors", {}).get("code") == "AI_PROVIDER_TIMEOUT"
        )

    @patch(
        "apps.ai.services.GeminiProvider.generate_json",
        side_effect=AIConfigurationError("GEMINI_API_KEY is not configured"),
    )
    def test_provider_unconfigured_handled(self, mock_gemini, api_client, user1, incident1):
        api_client.force_authenticate(user=user1)
        url = reverse("api:ai:incident-ai-investigate", args=[incident1.id])
        response = api_client.post(url, {"question": "Why did this happen?"}, format="json")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert (
            data.get("error_code") == "AI_CONFIGURATION_ERROR"
            or data.get("errors", {}).get("code") == "AI_CONFIGURATION_ERROR"
        )

    @patch(
        "apps.ai.services.GeminiProvider.generate_json",
        return_value={"invalid": "payload"},
    )
    def test_validation_error_handled(self, mock_gemini, api_client, user1, incident1):
        api_client.force_authenticate(user=user1)
        url = reverse("api:ai:incident-ai-investigate", args=[incident1.id])
        response = api_client.post(url, {"question": "Why did this happen?"}, format="json")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert (
            data.get("error_code") == "AI_VALIDATION_ERROR"
            or data.get("errors", {}).get("code") == "AI_VALIDATION_ERROR"
        )


@pytest.mark.django_db
class TestAIServiceLogic:
    """Test suite for AI context builder and similar incidents service."""

    def test_similar_incidents_are_project_scoped(self, project1, project2, incident1, incident2):
        # Create another incident in project 1
        inc1_prev = Incident.objects.create(
            project=project1,
            severity=Incident.Severity.CRITICAL,
            status=Incident.Status.RESOLVED,
            trigger_metadata={"metric_type": "FAILURE_RATE"},
        )
        IncidentPostmortem.objects.create(
            incident=inc1_prev,
            status=IncidentPostmortem.Status.COMPLETED,
            summary="Past DB overload",
            confirmed_root_cause="Redis connection leak",
        )

        similar = find_similar_incidents(incident1, limit=3)
        assert len(similar) == 1
        assert similar[0]["id"] == inc1_prev.id
        assert similar[0]["confirmed_root_cause"] == "Redis connection leak"

        # project2's incident2 must never appear
        assert all(s["id"] != incident2.id for s in similar)

    def test_ai_context_excludes_sensitive_fields(self, incident1):
        context = build_ai_context(incident1)
        context_json = str(context)

        assert "secret_123" not in context_json
        assert "[REDACTED]" in context["incident"]["trigger_metadata"]["api_token"]

    def test_ai_context_includes_representative_failed_executions_key(self, incident1):
        context = build_ai_context(incident1)
        assert "representative_failed_executions" in context
        # No job is linked to incident1, so the list must be empty (but present)
        assert context["representative_failed_executions"] == []


@pytest.fixture
def job1(project1):
    from apps.jobs.models import Job

    return Job.objects.create(
        project=project1,
        name="Worker Job",
        task_identifier="myapp.tasks.worker_job",
    )


@pytest.fixture
def incident_with_job(project1, job1):

    return Incident.objects.create(
        project=project1,
        job=job1,
        severity=Incident.Severity.CRITICAL,
        status=Incident.Status.OPEN,
        trigger_metadata={"metric_type": "FAILURE_RATE"},
    )


@pytest.fixture
def failed_execution(job1, incident_with_job):
    from django.utils import timezone
    from apps.executions.models import Execution

    return Execution.objects.create(
        job=job1,
        external_id="celery-task-aaa",
        status=Execution.Status.FAILED,
        last_event_at=timezone.now(),
        started_at=timezone.now(),
        finished_at=timezone.now(),
        error_type="ValueError",
        error_message="Something went wrong",
        traceback="Traceback (most recent call last):\n  File 'task.py', line 42, in run\nValueError: Something went wrong",
        worker="celery@worker-1",
        queue="default",
    )


@pytest.mark.django_db
class TestExecutionTraceback:
    """Test suite for execution error/traceback integration in AI context."""

    def test_traceback_included_in_context(self, incident_with_job, failed_execution):
        """Failed executions should appear in AI context."""
        context = build_ai_context(incident_with_job)
        execs = context["representative_failed_executions"]
        assert len(execs) >= 1
        entry = execs[0]
        assert entry["error_type"] == "ValueError"
        assert entry["error_message"] == "Something went wrong"
        assert "ValueError" in entry["traceback"]
        assert entry["worker"] == "celery@worker-1"
        assert entry["queue"] == "default"

    def test_traceback_bounded_to_max_size(self, incident_with_job, job1):
        """Tracebacks exceeding ~10 KB must be truncated."""
        from apps.ai.services import _sanitize_traceback, _TRACEBACK_MAX_BYTES

        big_traceback = "x" * 50_000
        result = _sanitize_traceback(big_traceback)
        assert len(result.encode("utf-8")) <= _TRACEBACK_MAX_BYTES + len(b"[...truncated...]\n")
        assert result.startswith("[...truncated...]")

    def test_secrets_redacted_from_traceback(self):
        """Token and password values in tracebacks must be redacted."""
        from apps.ai.services import _sanitize_traceback

        tb = "token='super_secret_value_abc123'\npassword='hunter2xyz'\nraised ValueError"
        result = _sanitize_traceback(tb)
        assert "super_secret_value_abc123" not in result
        assert "hunter2xyz" not in result
        assert "[REDACTED]" in result

    def test_credential_url_redacted_from_traceback(self):
        """Credential-bearing URLs in tracebacks must be replaced."""
        from apps.ai.services import _sanitize_traceback

        tb = "connecting to https://admin:mysecret@db.internal.example.com/prod"
        result = _sanitize_traceback(tb)
        assert "mysecret" not in result
        assert "[REDACTED_URL]" in result

    def test_duplicate_error_signatures_deduplicated(self, incident_with_job, job1):
        """Multiple executions with the same error should only appear once."""
        from django.utils import timezone
        from apps.executions.models import Execution
        from apps.ai.services import get_representative_failed_executions

        # Create 3 identical-signature executions
        for i in range(3):
            Execution.objects.create(
                job=job1,
                external_id=f"celery-dup-{i}",
                status=Execution.Status.FAILED,
                last_event_at=timezone.now(),
                error_type="ValueError",
                error_message="Same error every time",
            )

        results = get_representative_failed_executions(incident_with_job, limit=3)
        # All 3 share the same signature; only one should be selected
        matching = [r for r in results if r["error_message"] == "Same error every time"]
        assert len(matching) == 1

    def test_distinct_errors_all_selected(self, incident_with_job, job1):
        """Up to 3 distinct error signatures should each be represented."""
        from django.utils import timezone
        from apps.executions.models import Execution
        from apps.ai.services import get_representative_failed_executions

        error_types = ["KeyError", "IOError", "RuntimeError"]
        for i, et in enumerate(error_types):
            Execution.objects.create(
                job=job1,
                external_id=f"celery-distinct-{i}",
                status=Execution.Status.FAILED,
                last_event_at=timezone.now(),
                error_type=et,
                error_message=f"{et} happened",
            )

        results = get_representative_failed_executions(incident_with_job, limit=3)
        result_types = {r["error_type"] for r in results}
        for et in error_types:
            assert et in result_types

    def test_no_job_returns_empty_list(self, incident1):
        """An incident without a linked job must return an empty execution list."""
        from apps.ai.services import get_representative_failed_executions

        results = get_representative_failed_executions(incident1, limit=3)
        assert results == []

    def test_execution_project_isolation(self, incident_with_job, project2, team2, user2):
        """Executions from a different project's jobs must never appear."""
        from django.utils import timezone
        from apps.executions.models import Execution
        from apps.jobs.models import Job
        from apps.ai.services import get_representative_failed_executions

        # Create a job + execution in project2 (different team)
        other_job = Job.objects.create(
            project=project2,
            name="Other Job",
            task_identifier="other.tasks.job",
        )
        Execution.objects.create(
            job=other_job,
            external_id="celery-other-project",
            status=Execution.Status.FAILED,
            last_event_at=timezone.now(),
            error_type="PermissionError",
            error_message="Cross-project error",
        )

        results = get_representative_failed_executions(incident_with_job, limit=3)
        for r in results:
            assert r.get("error_message") != "Cross-project error"

    def test_empty_traceback_handled_gracefully(self):
        """Empty traceback strings must return empty string without error."""
        from apps.ai.services import _sanitize_traceback

        assert _sanitize_traceback("") == ""
        assert _sanitize_traceback(None) == ""  # type: ignore[arg-type]
