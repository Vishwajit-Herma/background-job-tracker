import pytest
from apps.jobs.models import Job
from apps.projects.models import Project
from apps.teams.models import Team
from apps.users.models import User


@pytest.fixture
def user(db):
    return User.objects.create(email="test@example.com", password="password")


@pytest.fixture
def project(user):
    team = Team.objects.create(name="T1", owner=user)
    return Project.objects.create(name="P1", team=team)


@pytest.mark.django_db
def test_audit_model_soft_delete(user, project):
    obj = Job.objects.create(task_identifier="Test1", project=project, created_by=user)
    assert not obj.is_deleted
    assert obj.deleted_at is None
    assert obj.deleted_by is None

    # Perform soft delete
    obj.soft_delete(user=user)
    obj.refresh_from_db()

    assert obj.is_deleted
    assert obj.deleted_at is not None
    assert obj.deleted_by == user


@pytest.mark.django_db
def test_audit_managers(user, project):
    Job.objects.create(task_identifier="Active1", project=project, created_by=user)
    obj2 = Job.objects.create(task_identifier="Deleted1", project=project, created_by=user)
    obj2.soft_delete(user=user)

    assert Job.objects.count() == 1
    assert Job.all_objects.count() == 2
    assert Job.deleted_objects.count() == 1


@pytest.mark.django_db
def test_audit_model_restore(user, project):
    obj = Job.objects.create(task_identifier="TestRestore", project=project, created_by=user)
    obj.soft_delete(user=user)
    assert obj.is_deleted

    obj.restore(user=user)
    obj.refresh_from_db()

    assert not obj.is_deleted
    assert obj.deleted_at is None
    assert obj.deleted_by is None
