import pytest
from django.db import models
from apps.config_management.models import AuditModel
from apps.users.models import User


# Define a concrete model for testing
class DummyAuditModel(AuditModel):
    name = models.CharField(max_length=50)

    class Meta:
        app_label = "config_management"


@pytest.fixture
def user(db):
    return User.objects.create(email="test@example.com", password="password")


@pytest.mark.django_db
def test_audit_model_soft_delete(user):
    obj = DummyAuditModel.objects.create(name="Test1", created_by=user)
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
def test_audit_managers(user):
    DummyAuditModel.objects.create(name="Active1", created_by=user)
    obj2 = DummyAuditModel.objects.create(name="Deleted1", created_by=user)
    obj2.soft_delete(user=user)

    assert DummyAuditModel.objects.count() == 1
    assert DummyAuditModel.all_objects.count() == 2
    assert DummyAuditModel.deleted_objects.count() == 1


@pytest.mark.django_db
def test_audit_model_restore(user):
    obj = DummyAuditModel.objects.create(name="TestRestore", created_by=user)
    obj.soft_delete(user=user)
    assert obj.is_deleted

    obj.restore(user=user)
    obj.refresh_from_db()

    assert not obj.is_deleted
    assert obj.deleted_at is None
    assert obj.deleted_by is None
