import pytest
from datetime import timedelta
from django.utils import timezone
from django.db import models

from apps.config_management.models import AuditModel
from apps.config_management.tasks import hard_delete_soft_deleted_records
from apps.users.models import User


class TaskDummyAuditModel(AuditModel):
    name = models.CharField(max_length=50)

    class Meta:
        app_label = "config_management"


@pytest.fixture
def user(db):
    return User.objects.create(email="task_test@example.com", password="password")


@pytest.mark.django_db
def test_hard_delete_soft_deleted_records(user):
    # 1. Active record (should not be touched)
    TaskDummyAuditModel.objects.create(name="Active", created_by=user)

    # 2. Recently soft-deleted record (should not be touched, < 30 days)
    recent_deleted = TaskDummyAuditModel.objects.create(name="Recent", created_by=user)
    recent_deleted.soft_delete(user=user)

    # 3. Old soft-deleted record (should be hard deleted, > 30 days)
    old_deleted = TaskDummyAuditModel.objects.create(name="Old", created_by=user)
    old_deleted.soft_delete(user=user)

    # Manually backdate the deleted_at using update() to avoid auto_now behavior
    TaskDummyAuditModel.all_objects.filter(id=old_deleted.id).update(
        deleted_at=timezone.now() - timedelta(days=31)
    )

    assert TaskDummyAuditModel.all_objects.count() == 3

    # Run the celery task synchronously
    deleted_count = hard_delete_soft_deleted_records()

    # Verify only the old_deleted record was removed
    assert deleted_count == 1
    assert TaskDummyAuditModel.all_objects.count() == 2
    assert TaskDummyAuditModel.objects.count() == 1
    assert TaskDummyAuditModel.deleted_objects.count() == 1

    # Ensure it was the "Old" one that was deleted
    assert not TaskDummyAuditModel.all_objects.filter(name="Old").exists()
