from django.contrib import admin
from .models import NotificationChannel, NotificationPolicy, NotificationDelivery, InAppNotification


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "type", "is_active", "created_at"]
    list_filter = ["type", "is_active", "project"]
    search_fields = ["name", "project__name"]


@admin.register(NotificationPolicy)
class NotificationPolicyAdmin(admin.ModelAdmin):
    list_display = ["__str__", "project", "channel", "severity", "is_active", "created_at"]
    list_filter = ["severity", "is_active", "project", "channel__type"]
    search_fields = ["project__name", "channel__name"]


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ["id", "incident_event", "channel", "status", "attempt_count", "last_attempt_at"]
    list_filter = ["status", "channel__type"]
    search_fields = ["incident_event__id", "channel__name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(InAppNotification)
class InAppNotificationAdmin(admin.ModelAdmin):
    list_display = ["id", "recipient", "title", "is_read", "read_at", "created_at"]
    list_filter = ["is_read", "created_at"]
    search_fields = ["recipient__email", "title"]
    readonly_fields = ["created_at"]
