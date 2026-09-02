from datetime import timedelta
import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone

from apps.executions.models import Execution, ExecutionEvent
from apps.incidents.models import Incident
from apps.jobs.models import Job
from apps.projects.models import Project, Team

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def user1(db):
    return User.objects.create_user(email="db_index_user@example.com", password="password")


@pytest.fixture
def project1(db, user1):
    team = Team.objects.create(name="DB Index Team", owner=user1)
    return Project.objects.create(team=team, name="DB Index Project")


class TestDBIndexes:
    def explain_query(self, qs):
        compiler = qs.query.get_compiler(using=qs.db)
        sql, params = compiler.as_sql()
        with connection.cursor() as cursor:
            cursor.execute("EXPLAIN " + sql, params)
            return cursor.fetchall()

    def test_expected_indexes_defined_on_models(self):
        """Verify that justified performance indexes are declared on the models."""
        execution_indexes = [list(idx.fields) for idx in Execution._meta.indexes]
        assert ["job", "-started_at"] in execution_indexes
        assert ["job", "status"] in execution_indexes
        assert ["created_at"] in execution_indexes

        event_indexes = [list(idx.fields) for idx in ExecutionEvent._meta.indexes]
        assert ["execution", "-event_timestamp"] in event_indexes
        assert ["event_timestamp"] in event_indexes

        incident_indexes = [list(idx.fields) for idx in Incident._meta.indexes]
        assert ["project", "status"] in incident_indexes

    def test_query_plans_execute_with_representative_data(self, project1):
        """Inspect query execution plans with representative data without strictly requiring index scan."""
        job = Job.objects.create(project=project1, name="Index Test", task_identifier="index_test")
        now = timezone.now()

        # Create representative execution dataset
        executions = []
        for i in range(100):
            executions.append(
                Execution(
                    job=job,
                    external_id=f"idx_exec_{i}",
                    status=Execution.Status.SUCCESS if i % 5 != 0 else Execution.Status.FAILED,
                    last_event_at=now - timedelta(minutes=i),
                    started_at=now - timedelta(minutes=i),
                    duration_ms=100 + i,
                )
            )
        Execution.objects.bulk_create(executions)

        # 1. Job + Time Range Query
        qs1 = Execution.objects.filter(job=job, started_at__gte=now - timedelta(hours=2))
        plan1 = self.explain_query(qs1)
        assert len(plan1) > 0

        # 2. Job + Status Filter Query
        qs2 = Execution.objects.filter(job=job, status=Execution.Status.FAILED)
        plan2 = self.explain_query(qs2)
        assert len(plan2) > 0

        # 3. Incident Filter Query
        Incident.objects.create(
            project=project1,
            job=job,
            status=Incident.Status.OPEN,
            severity=Incident.Severity.CRITICAL,
        )
        qs3 = Incident.objects.filter(project=project1, status=Incident.Status.OPEN)
        plan3 = self.explain_query(qs3)
        assert len(plan3) > 0
