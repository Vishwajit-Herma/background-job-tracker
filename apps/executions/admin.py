from django.contrib import admin
from django.utils.timezone import localtime
from .models import Execution, ExecutionEvent


@admin.register(Execution)
class ExecutionAdmin(admin.ModelAdmin):
    """
    Read-only operational data view for Executions.
    Optimized for high-volume admin deletion and querying without 500 memory timeouts.
    """

    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "external_id",
        "job",
        "status",
        "formatted_started_at",
        "formatted_finished_at",
        "duration_ms",
        "queue",
        "worker",
        "retry_count",
        "created_at",
    )
    list_filter = ("status", "queue", "worker", "job__project")
    search_fields = ("external_id", "job__task_identifier", "error_message", "error_type")
    list_select_related = ("job", "job__project")
    actions = ["fast_bulk_delete"]

    @admin.action(description="Fast Bulk Delete Selected Executions (Prevents 500 Timeout)")
    def fast_bulk_delete(self, request, queryset):
        total_deleted = 0
        batch_size = 1000
        while True:
            batch_ids = list(queryset.values_list("id", flat=True)[:batch_size])
            if not batch_ids:
                break
            deleted_count, _ = Execution.objects.filter(id__in=batch_ids).delete()
            total_deleted += deleted_count

        self.message_user(
            request,
            f"Successfully deleted {total_deleted} execution(s).",
        )

    def delete_queryset(self, request, queryset):
        batch_size = 1000
        while True:
            batch_ids = list(queryset.values_list("id", flat=True)[:batch_size])
            if not batch_ids:
                break
            Execution.objects.filter(id__in=batch_ids).delete()

    @admin.display(description="Started At", ordering="started_at")
    def formatted_started_at(self, obj):
        if obj.started_at:
            return localtime(obj.started_at).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        return "-"

    @admin.display(description="Finished At", ordering="finished_at")
    def formatted_finished_at(self, obj):
        if obj.finished_at:
            return localtime(obj.finished_at).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        return "-"

    # Executions should not be manually created or edited in the admin.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ExecutionEvent)
class ExecutionEventAdmin(admin.ModelAdmin):
    """
    Read-only operational data view for Execution Events.
    Optimized for high-volume admin querying without 500 memory timeouts.
    """

    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "event_id",
        "execution",
        "status",
        "formatted_event_timestamp",
        "received_at",
        "queue",
        "worker",
        "retry_count",
    )
    list_filter = ("status", "queue", "worker")
    search_fields = ("event_id", "execution__external_id", "error_message", "error_type")
    list_select_related = ("execution", "execution__job")
    actions = ["fast_bulk_delete"]

    @admin.action(description="Fast Bulk Delete Selected Execution Events (Prevents 500 Timeout)")
    def fast_bulk_delete(self, request, queryset):
        total_deleted = 0
        batch_size = 1000
        while True:
            batch_ids = list(queryset.values_list("id", flat=True)[:batch_size])
            if not batch_ids:
                break
            deleted_count, _ = ExecutionEvent.objects.filter(id__in=batch_ids).delete()
            total_deleted += deleted_count

        self.message_user(
            request,
            f"Successfully deleted {total_deleted} execution event(s).",
        )

    def delete_queryset(self, request, queryset):
        batch_size = 1000
        while True:
            batch_ids = list(queryset.values_list("id", flat=True)[:batch_size])
            if not batch_ids:
                break
            ExecutionEvent.objects.filter(id__in=batch_ids).delete()

    @admin.display(description="Event Timestamp", ordering="event_timestamp")
    def formatted_event_timestamp(self, obj):
        if obj.event_timestamp:
            return localtime(obj.event_timestamp).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        return "-"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
