from django.contrib import admin
from .models import Execution, ExecutionEvent


@admin.register(Execution)
class ExecutionAdmin(admin.ModelAdmin):
    """
    Read-only operational data view for Executions.
    """

    list_display = (
        "external_id",
        "job",
        "status",
        "started_at",
        "finished_at",
        "duration_ms",
        "queue",
        "worker",
        "retry_count",
        "created_at",
    )
    list_filter = ("status", "queue", "worker", "job__project")
    search_fields = ("external_id", "job__task_identifier", "error_message", "error_type")
    list_select_related = ("job", "job__project")

    # Executions should not be manually created, edited, or deleted in the admin.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ExecutionEvent)
class ExecutionEventAdmin(admin.ModelAdmin):
    """
    Read-only operational data view for Execution Events.
    """

    list_display = (
        "event_id",
        "execution",
        "status",
        "event_timestamp",
        "received_at",
        "queue",
        "worker",
        "retry_count",
    )
    list_filter = ("status", "queue", "worker")
    search_fields = ("event_id", "execution__external_id", "error_message", "error_type")
    list_select_related = ("execution", "execution__job")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
