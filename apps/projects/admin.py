from django.contrib import admin
from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Admin configuration for Project model."""

    list_display = (
        "name",
        "team",
        "is_deleted",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_deleted", "team")
    search_fields = ("name", "description", "team__name")
    readonly_fields = (
        "created_at",
        "updated_at",
        "created_by",
        "modified_by",
        "deleted_at",
        "deleted_by",
    )

    # Optional: separate fields into fieldsets for cleaner UI
    fieldsets = (
        (None, {"fields": ("name", "team", "description")}),
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
