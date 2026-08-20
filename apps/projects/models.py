import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.config_management.models import AuditModel
from apps.teams.models import Team


class Project(AuditModel):
    """
    Project model representing a monitored application or environment.
    Belongs to a Team.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="projects",
        verbose_name=_("team"),
    )
    name = models.CharField(_("project name"), max_length=255)
    description = models.TextField(_("description"), blank=True)
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

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


class APIKey(AuditModel):
    """
    API Key scoped to a single Project.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="api_keys", verbose_name=_("project")
    )
    name = models.CharField(_("key name"), max_length=255)
    key_prefix = models.CharField(_("key prefix"), max_length=32)
    key_hash = models.CharField(_("key hash"), max_length=128)

    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_api_keys",
        verbose_name=_("revoked by"),
    )

    class Meta:
        verbose_name = _("API key")
        verbose_name_plural = _("API keys")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"],
                condition=models.Q(is_deleted=False),
                name="unique_active_apikey_name_per_project",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.key_prefix}...)"

    @property
    def is_revoked(self):
        return self.revoked_at is not None

    @classmethod
    def create_key(cls, project, name, user):
        """
        Securely generate a new API key.
        Returns a tuple of (APIKey instance, raw_key_string).
        """
        raw_key = f"rk_live_{secrets.token_urlsafe(32)}"
        key_prefix = raw_key[:12]
        key_hash = make_password(raw_key)

        instance = cls(
            project=project,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
        )
        instance.created_by = user
        instance.modified_by = user
        instance.save()
        return instance, raw_key

    def verify_key(self, raw_key):
        """
        Verify the given raw key against the stored hash.
        Returns False if the key is revoked or does not match.
        """
        if self.is_revoked:
            return False
        return check_password(raw_key, self.key_hash)
