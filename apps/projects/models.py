from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.config_management.models import AuditModel
from apps.teams.models import Team


class Project(AuditModel):
    """
    Project model representing a monitored application or environment.
    Belongs to a Team.
    """

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="projects",
        verbose_name=_("team"),
    )
    name = models.CharField(_("project name"), max_length=255)
    description = models.TextField(_("description"), blank=True)

    class Meta:
        verbose_name = _("project")
        verbose_name_plural = _("projects")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "name"],
                condition=models.Q(is_deleted=False),
                name="unique_active_project_name_per_team",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.team.name})"
