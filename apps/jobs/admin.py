from django.contrib import admin
from .models import Job, TaskRegistry


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "project",
        "task_identifier",
        "status",
        "verification_status",
        "is_deleted",
        "created_at",
        "updated_at",
    )
    list_filter = ("project", "status", "verification_status", "is_deleted")
    search_fields = ("name", "task_identifier", "project__name")

    def get_queryset(self, request):
        # Allow viewing soft-deleted jobs in the admin, similar to Project
        qs = Job.all_objects.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


@admin.register(TaskRegistry)
class TaskRegistryAdmin(admin.ModelAdmin):
    list_display = (
        "task_identifier",
        "project",
        "first_seen_at",
        "last_seen_at",
    )
    list_filter = ("project",)
    search_fields = ("task_identifier", "project__name")
