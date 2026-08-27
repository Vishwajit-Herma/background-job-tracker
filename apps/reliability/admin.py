from django.contrib import admin
from apps.reliability.models import JobExpectation, JobBaseline, ReliabilityFinding


@admin.register(JobExpectation)
class JobExpectationAdmin(admin.ModelAdmin):
    list_display = (
        "job",
        "expected_interval_seconds",
        "max_runtime_seconds",
        "is_enabled",
        "updated_at",
    )
    list_filter = ("is_enabled",)
    search_fields = ("job__name", "job__task_identifier")


@admin.register(JobBaseline)
class JobBaselineAdmin(admin.ModelAdmin):
    list_display = (
        "job",
        "is_sufficient",
        "median_interval_seconds",
        "p95_runtime_ms",
        "calculated_at",
    )
    list_filter = ("is_sufficient",)
    search_fields = ("job__name", "job__task_identifier")


@admin.register(ReliabilityFinding)
class ReliabilityFindingAdmin(admin.ModelAdmin):
    list_display = ("job", "condition_type", "status", "severity", "detected_at", "recovered_at")
    list_filter = ("condition_type", "status", "severity")
    search_fields = ("job__name", "job__task_identifier")
