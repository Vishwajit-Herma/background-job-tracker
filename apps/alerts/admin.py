# Register your models here.

from django.contrib import admin
from .models import AlertRule


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ["id", "project", "job", "metric", "threshold", "is_active", "created_at"]
    list_filter = ["is_active", "metric", "project"]
    search_fields = ["project__name", "job__name"]
