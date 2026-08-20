from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditQuerySet(models.QuerySet):
    """
    QuerySet providing helper methods to filter records by
    their soft-delete status.

    Examples:
        Project.all_objects.active()     # is_deleted=False
        Project.all_objects.deleted()    # is_deleted=True
    """

    def active(self):
        """
        Return only active (non-deleted) records.
        """
        return self.filter(is_deleted=False)

    def deleted(self):
        """
        Return only soft-deleted records.
        """
        return self.filter(is_deleted=True)


AuditManager = models.Manager.from_queryset(AuditQuerySet)


class ActiveManager(AuditManager):
    """
    Default manager that returns only active records
    (`is_deleted=False`).

    Examples:
        Job.objects.all()
        Job.objects.filter(name__icontains="Backup")
    """

    def get_queryset(self):
        return super().get_queryset().active()


class DeletedManager(AuditManager):
    """
    Manager that returns only soft-deleted records
    (`is_deleted=True`).

    Examples:
        Job.deleted_objects.all()
        Job.deleted_objects.filter(created_by=user)
    """

    def get_queryset(self):
        return super().get_queryset().deleted()


class AuditModel(models.Model):
    """
    Abstract base model providing audit fields, soft-delete
    support, and managers for querying records.

    Managers:
        objects
            Returns records where `is_deleted=False`.

        all_objects
            Returns all records.

        deleted_objects
            Returns records where `is_deleted=True`.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_created",
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_modified",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_deleted",
    )
    is_deleted = models.BooleanField(default=False)

    # Managers
    objects = ActiveManager()  # Default manager (Active only)
    all_objects = AuditManager()  # All records
    deleted_objects = DeletedManager()  # Deleted only

    class Meta:
        abstract = True

    def soft_delete(self, user=None) -> None:
        """
        Mark the object as soft-deleted.
        """
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user is not None:
            self.deleted_by = user
            self.modified_by = user

        self.save(
            update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at", "modified_by"]
        )

    def restore(self, user=None) -> None:
        """
        Restore a soft-deleted object.
        """
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        if user is not None:
            self.modified_by = user

        self.save(
            update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at", "modified_by"]
        )
