import pytest
from datetime import timedelta
from django.utils import timezone
from apps.jobs.models import Job
from apps.projects.models import Project
from apps.teams.models import Team
from apps.users.models import User
from apps.config_management.tasks import hard_delete_soft_deleted_records


@pytest.fixture
def user(db):
    return User.objects.create(email="test@example.com", password="password")


@pytest.fixture
def project(user):
    team = Team.objects.create(name="T1", owner=user)
    return Project.objects.create(name="P1", team=team)


@pytest.mark.django_db
def test_hard_delete_task(user, project):
    # Active record
    Job.objects.create(task_identifier="Active", project=project, created_by=user)

    # Recently soft-deleted (should not be hard-deleted)
    recent_deleted = Job.objects.create(task_identifier="Recent", project=project, created_by=user)
    recent_deleted.soft_delete(user=user)

    # Old soft-deleted (should be hard-deleted)
    old_deleted = Job.objects.create(task_identifier="Old", project=project, created_by=user)
    old_deleted.soft_delete(user=user)

    # Manually backdate deleted_at to older than 30 days
    Job.all_objects.filter(id=old_deleted.id).update(deleted_at=timezone.now() - timedelta(days=35))

    assert Job.all_objects.count() == 3

    # Run celery task
    result = hard_delete_soft_deleted_records()
    assert result == 1

    # Verify counts
    assert Job.all_objects.count() == 2
    assert Job.objects.count() == 1
    assert Job.deleted_objects.count() == 1

    # Verify specific record was deleted
    assert not Job.all_objects.filter(task_identifier="Old").exists()
