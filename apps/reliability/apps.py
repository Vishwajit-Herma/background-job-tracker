from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ReliabilityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reliability"
    verbose_name = _("Reliability")
