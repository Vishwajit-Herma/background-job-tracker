from django.contrib import admin
from .models import Project, APIKey


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Admin configuration for Project model."""

    list_display = (
        "name",
        "team",
        "status",
        "is_deleted",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "is_deleted", "team")
    search_fields = ("name", "description", "team__name")
    readonly_fields = (
        "created_at",
        "updated_at",
        "created_by",
        "modified_by",
        "deleted_at",
        "deleted_by",
    )

    fieldsets = (
        (None, {"fields": ("name", "team", "description", "status")}),
        (
            "Audit Info",
            {
                "fields": (
                    "is_deleted",
                    "created_at",
                    "created_by",
                    "updated_at",
                    "modified_by",
                    "deleted_at",
                    "deleted_by",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        """Use all_objects so soft-deleted projects remain visible in the admin."""
        qs = self.model.all_objects.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    """Admin configuration for APIKey model."""

    list_display = (
        "name",
        "project",
        "key_prefix",
        "is_revoked",
        "created_at",
        "revoked_at",
    )
    list_filter = ("project",)
    search_fields = ("name", "key_prefix", "project__name")
    readonly_fields = (
        "key_prefix",
        "key_hash",
        "created_at",
        "updated_at",
        "created_by",
        "modified_by",
        "revoked_at",
        "revoked_by",
    )
    exclude = ("key_hash",)  # Never show the hash in the admin form

    fieldsets = (
        (None, {"fields": ("project", "name", "key_prefix")}),
        (
            "Revocation Info",
            {
                "fields": ("revoked_at", "revoked_by"),
            },
        ),
        (
            "Audit Info",
            {
                "fields": (
                    "created_at",
                    "created_by",
                    "updated_at",
                    "modified_by",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        return False  # Keys should only be created via the API

    def has_change_permission(self, request, obj=None):
        return False  # Keys should not be edited via admin
