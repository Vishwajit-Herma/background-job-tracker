from datetime import timedelta
import time
import pytest

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.executions.models import Execution
from apps.jobs.models import Job
from apps.projects.models import Project, Team

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def user1(db):
    return User.objects.create_user(email="perf_user@example.com", password="password")


@pytest.fixture
def project1(db, user1):
    team = Team.objects.create(name="Perf Team", owner=user1)
    return Project.objects.create(team=team, name="Perf Project")


class TestLargeDatasetsPerformance:
    @pytest.fixture
    def large_dataset(self, project1):
        job = Job.objects.create(project=project1, name="Perf Job", task_identifier="perf_job")
        now = timezone.now()

        # 5000 executions for standard CI performance checks
        executions = []
        for i in range(5000):
            status = Execution.Status.SUCCESS if i % 10 != 0 else Execution.Status.FAILED
            executions.append(
                Execution(
                    job=job,
                    external_id=f"ext_perf_{i}",
                    status=status,
                    last_event_at=now - timedelta(minutes=i),
                    started_at=now - timedelta(minutes=i, seconds=10),
                    finished_at=now - timedelta(minutes=i),
                    duration_ms=10000,
                )
            )
        Execution.objects.bulk_create(executions, batch_size=1000)
        return job

    def test_execution_list_pagination_performance(self, api_client, user1, large_dataset):
        api_client.force_authenticate(user=user1)
        url = reverse("api:executions:execution-list") + f"?job={large_dataset.id}"

        start_time = time.perf_counter()
        response = api_client.get(url)
        duration = time.perf_counter() - start_time

        assert response.status_code == status.HTTP_200_OK
        # Verify pagination bounding (should be fast, e.g. < 500ms)
        assert duration < 0.5, f"Execution listing took too long: {duration:.4f}s"
        assert len(response.data["data"]) <= 100  # Default pagination

    def test_analytics_aggregation_performance(self, api_client, user1, large_dataset):
        api_client.force_authenticate(user=user1)
        url = f"/api/projects/{large_dataset.project_id}/analytics/"

        start_time = time.perf_counter()
        response = api_client.get(url)
        duration = time.perf_counter() - start_time

        assert response.status_code == status.HTTP_200_OK
        # Verify analytics aggregation is fast (< 500ms) even with 5000 executions
        assert duration < 0.5, f"Analytics aggregation took too long: {duration:.4f}s"

    def test_ai_context_remains_bounded(self, large_dataset):
        from apps.ai.services import build_ai_context
        from apps.incidents.models import Incident

        incident = Incident.objects.create(
            project=large_dataset.project,
            job=large_dataset,
            status=Incident.Status.OPEN,
            severity=Incident.Severity.CRITICAL,
        )

        start_time = time.perf_counter()
        context = build_ai_context(incident)
        duration = time.perf_counter() - start_time

        # Gathering context even with 5000 executions should be fast since we only grab up to 3 failed executions
        assert duration < 0.5, f"AI context generation took too long: {duration:.4f}s"
        assert "representative_failed_executions" in context
        assert len(context["representative_failed_executions"]) <= 3

    def test_large_dataset_10k_performance(self, api_client, user1, project1):
        """Dedicated 10k+ execution check measuring listing and aggregation speed."""
        job_10k = Job.objects.create(
            project=project1, name="10k Job", task_identifier="task.perf_10k"
        )
        now = timezone.now()

        # Generate 10,000 executions in fast bulk insert
        executions = [
            Execution(
                job=job_10k,
                external_id=f"ext_10k_{i}",
                status=Execution.Status.SUCCESS if i % 8 != 0 else Execution.Status.FAILED,
                last_event_at=now - timedelta(seconds=i * 5),
                started_at=now - timedelta(seconds=i * 5, microseconds=100),
                finished_at=now - timedelta(seconds=i * 5),
                duration_ms=250,
            )
            for i in range(10000)
        ]
        Execution.objects.bulk_create(executions, batch_size=2500)

        api_client.force_authenticate(user=user1)

        # 1. Test Paginated Listing on 10k rows
        url_list = reverse("api:executions:execution-list") + f"?job={job_10k.id}"
        t0 = time.perf_counter()
        res_list = api_client.get(url_list)
        t_list = time.perf_counter() - t0

        assert res_list.status_code == status.HTTP_200_OK
        assert t_list < 0.8, f"10k listing took too long: {t_list:.4f}s"
        assert len(res_list.data["data"]) <= 100

        # 2. Test Project Analytics Aggregation on 10k rows
        url_analytics = f"/api/projects/{project1.id}/analytics/"
        t1 = time.perf_counter()
        res_analytics = api_client.get(url_analytics)
        t_analytics = time.perf_counter() - t1

        assert res_analytics.status_code == status.HTTP_200_OK
        assert t_analytics < 0.8, f"10k analytics aggregation took too long: {t_analytics:.4f}s"
