import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from apps.projects.models import Project
from apps.jobs.models import Job
from apps.executions.models import Execution
from apps.teams.models import Team
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def setup_data(db):
    user = User.objects.create(email="analytics@example.com")
    user.set_password("password")
    user.save()

    team = Team.objects.create(name="Analytics Team", slug="analytics", owner=user)

    project = Project.objects.create(team=team, name="Analytics Project")

    # Create jobs
    job1 = Job.objects.create(project=project, name="Job 1", task_identifier="task_1")
    job2 = Job.objects.create(project=project, name="Job 2", task_identifier="task_2")

    # Executions for Job 1
    now = timezone.now()
    Execution.objects.create(
        job=job1,
        external_id="j1_1",
        status="success",
        started_at=now - timedelta(hours=2),
        finished_at=now - timedelta(hours=2) + timedelta(seconds=1),
        duration_ms=1000,
        last_event_at=now,
    )
    Execution.objects.create(
        job=job1,
        external_id="j1_2",
        status="failed",
        started_at=now - timedelta(hours=1),
        finished_at=now - timedelta(hours=1) + timedelta(seconds=2),
        duration_ms=2000,
        last_event_at=now,
    )
    Execution.objects.create(
        job=job1,
        external_id="j1_3",
        status="success",
        started_at=now - timedelta(minutes=30),
        finished_at=now - timedelta(minutes=30) + timedelta(seconds=1),
        duration_ms=1500,
        last_event_at=now,
    )
    Execution.objects.create(
        job=job1,
        external_id="j1_4",
        status="success",
        started_at=now - timedelta(minutes=10),
        finished_at=now - timedelta(minutes=10) + timedelta(seconds=1),
        duration_ms=1500,
        last_event_at=now,
    )

    # Executions for Job 2
    Execution.objects.create(
        job=job2,
        external_id="j2_1",
        status="success",
        started_at=now - timedelta(hours=3),
        finished_at=now - timedelta(hours=3) + timedelta(seconds=5),
        duration_ms=5000,
        last_event_at=now,
    )

    return user, team, project, job1, job2


@pytest.mark.django_db
def test_job_analytics_aggregation(api_client, setup_data):
    user, _, _, job1, _ = setup_data
    api_client.force_authenticate(user=user)

    response = api_client.get(f"/api/jobs/{job1.id}/analytics/")
    assert response.status_code == status.HTTP_200_OK

    data = response.json().get("data", response.json())
    assert data["executions"] == 4
    assert data["successes"] == 3
    assert data["failures"] == 1
    assert data["success_rate"] == 75.0
    assert data["failure_rate"] == 25.0
    assert data["health"] == "CRITICAL"  # > 10%
    assert data["average_duration_ms"] == 1500
    assert data["p50_duration_ms"] is not None
    assert data["p95_duration_ms"] is not None


@pytest.mark.django_db
def test_project_analytics_aggregation(api_client, setup_data):
    user, _, project, _, _ = setup_data
    api_client.force_authenticate(user=user)

    response = api_client.get(f"/api/projects/{project.id}/analytics/")
    assert response.status_code == status.HTTP_200_OK

    data = response.json().get("data", response.json())
    assert data["executions"] == 5
    assert data["successes"] == 4
    assert data["failures"] == 1

    assert data["healthy_jobs"] == 1
    assert data["critical_jobs"] == 1
    assert data["degraded_jobs"] == 0
    assert data["health"] == "CRITICAL"

    # Top failing
    assert len(data["top_failing_jobs"]) == 1
    assert data["top_failing_jobs"][0]["failure_count"] == 1

    # Slowest jobs
    assert len(data["slowest_jobs"]) == 2
    assert data["slowest_jobs"][0]["average_duration_ms"] == 5000  # Job 2


@pytest.mark.django_db
def test_analytics_time_windows(api_client, setup_data):
    user, _, project, job1, _ = setup_data
    api_client.force_authenticate(user=user)

    # Test last_1_hour (should only catch j1_3 and j1_4)
    response = api_client.get(f"/api/jobs/{job1.id}/analytics/?range=last_1_hour")
    assert response.status_code == status.HTTP_200_OK
    data = response.json().get("data", response.json())
    assert data["executions"] == 2

    # Test custom range catching only first execution
    now = timezone.now()
    # DRF expects Z for UTC
    start = (now - timedelta(hours=2, minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now - timedelta(hours=1, minutes=55)).strftime("%Y-%m-%dT%H:%M:%SZ")

    response = api_client.get(f"/api/jobs/{job1.id}/analytics/?start={start}&end={end}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json().get("data", response.json())
    assert data["executions"] == 1


@pytest.mark.django_db
def test_tenant_isolation_analytics(api_client, setup_data):
    _, _, project, job1, _ = setup_data

    # New user in a different team
    hacker = User.objects.create(email="hacker@example.com")
    Team.objects.create(name="Hacker Team", slug="hacker", owner=hacker)
    api_client.force_authenticate(user=hacker)

    response = api_client.get(f"/api/jobs/{job1.id}/analytics/")
    assert response.status_code == status.HTTP_404_NOT_FOUND

    response = api_client.get(f"/api/projects/{project.id}/analytics/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_analytics_query_efficiency(api_client, django_assert_max_num_queries):
    """
    Ensure we don't have N+1 queries when fetching Project analytics with many jobs.
    """
    user = User.objects.create(email="perf@example.com")
    team = Team.objects.create(name="Perf Team", slug="perf", owner=user)
    project = Project.objects.create(team=team, name="Perf Project")

    now = timezone.now()

    # Create 50 jobs, each with 5 executions
    for i in range(50):
        j = Job.objects.create(project=project, name=f"Perf Job {i}", task_identifier=f"perf_{i}")
        executions = []
        for e in range(5):
            executions.append(
                Execution(
                    job=j,
                    external_id=f"p{i}_e{e}",
                    status="success",
                    started_at=now,
                    finished_at=now,
                    duration_ms=100,
                    last_event_at=now,
                )
            )
        Execution.objects.bulk_create(executions)

    api_client.force_authenticate(user=user)

    # Allow a small buffer for query execution plans, rather than exact counts
    with django_assert_max_num_queries(15):
        response = api_client.get(f"/api/projects/{project.id}/analytics/")
        assert response.status_code == status.HTTP_200_OK

        data = response.json().get("data", response.json())
        assert data["executions"] == 250
        assert data["healthy_jobs"] == 50
