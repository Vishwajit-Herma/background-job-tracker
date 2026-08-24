# Register your models here.

from django.contrib import admin
from .models import Incident, IncidentEvent, IncidentNote


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ["id", "project", "job", "status", "severity", "assigned_to", "created_at"]
    list_filter = ["status", "severity", "project"]
    search_fields = ["project__name", "job__name"]


class ReadOnlyAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # def has_delete_permission(self, request, obj=None):
    #     return False


@admin.register(IncidentEvent)
class IncidentEventAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["id", "incident", "event_type", "event_time"]
    list_filter = ["event_type"]


@admin.register(IncidentNote)
class IncidentNoteAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["id", "incident", "author", "created_at"]
