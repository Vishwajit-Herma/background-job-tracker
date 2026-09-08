from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError
from .models import NotificationChannel, NotificationPolicy, InAppNotification
from apps.teams.models import TeamMember


class NotificationChannelSerializer(serializers.ModelSerializer):
    """
    Serializer for NotificationChannel model. Validates webhook and email configs.
    """

    class Meta:
        model = NotificationChannel
        fields = [
            "id",
            "project",
            "type",
            "name",
            "config",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        type_ = attrs.get("type") or (self.instance.type if self.instance else None)
        config = attrs.get("config") or (self.instance.config if self.instance else {})
        project = attrs.get("project") or (self.instance.project if self.instance else None)

        if type_ == NotificationChannel.ChannelType.WEBHOOK:
            if "url" not in config:
                raise DRFValidationError({"config": "Webhook config must contain 'url'."})
            if "secret" not in config and not (
                self.instance and self.instance.config.get("secret")
            ):
                # If secret is ********, it's bypassed in perform_update, but we need to pass validation here
                raise DRFValidationError({"config": "Webhook config must contain 'secret'."})

            secret = config.get("secret", "")
            if (
                secret != "********"
                and len(secret) < 16
                and not (self.instance and self.instance.config.get("secret"))
            ):
                # Only enforce length if they are providing a new secret that isn't the masked value
                raise DRFValidationError(
                    {"config": "Webhook secret must be at least 16 characters long."}
                )
            elif secret != "********" and len(secret) < 16 and secret != "":
                raise DRFValidationError(
                    {"config": "Webhook secret must be at least 16 characters long."}
                )

            url = config.get("url", "")
            allow_insecure = config.get("allow_insecure_http", False)
            if url.startswith("http://") and not allow_insecure:
                raise DRFValidationError(
                    {"config": "HTTPS is required for webhooks unless allow_insecure_http is true."}
                )
            if not url.startswith("http://") and not url.startswith("https://"):
                raise DRFValidationError({"config": "Webhook URL must start with http or https."})
        elif type_ == NotificationChannel.ChannelType.EMAIL:
            target = config.get("recipient_target", "").upper()
            recipients = config.get("recipients", [])

            if not target:
                if isinstance(recipients, list) and recipients:
                    target = "CUSTOM"
                    config["recipient_target"] = "CUSTOM"
                else:
                    target = "ALL"
                    config["recipient_target"] = "ALL"

            if target not in ["ALL", "ADMINS", "OWNERS", "CUSTOM"]:
                raise DRFValidationError(
                    {
                        "config": "Email config 'recipient_target' must be 'ALL', 'ADMINS', 'OWNERS', or 'CUSTOM'."
                    }
                )

            if target == "CUSTOM" and (not isinstance(recipients, list) or not recipients):
                raise DRFValidationError(
                    {"config": "Email config with 'CUSTOM' target must contain 'recipients' list."}
                )

            if project and target in ["ALL", "ADMINS", "OWNERS"]:
                members_qs = TeamMember.objects.filter(
                    team=project.team, is_active=True, user__is_active=True
                )
                if target == "ADMINS":
                    members_qs = members_qs.filter(role__in=["owner", "admin"])
                elif target == "OWNERS":
                    members_qs = members_qs.filter(role="owner")

                if not members_qs.exists():
                    raise DRFValidationError(
                        {
                            "config": f"No active team members with role target '{target}' exist for this project."
                        }
                    )

        project = attrs.get("project") or (self.instance.project if self.instance else None)
        name = attrs.get("name") or (self.instance.name if self.instance else None)

        if project and type_ and name:
            channel_qs = NotificationChannel.objects.filter(project=project, type=type_, name=name)
            if self.instance:
                channel_qs = channel_qs.exclude(pk=self.instance.pk)
            if channel_qs.exists():
                raise DRFValidationError(
                    {
                        "name": "A notification channel with this name and type already exists for this project."
                    }
                )

        if project and type_ and config:
            config_qs = NotificationChannel.objects.filter(
                project=project, type=type_, config=config
            )
            if self.instance:
                config_qs = config_qs.exclude(pk=self.instance.pk)
            if config_qs.exists():
                raise DRFValidationError(
                    {
                        "config": "A notification channel with this configuration already exists for this project."
                    }
                )

        return attrs

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Mask the secret if it exists
        if instance.type == NotificationChannel.ChannelType.WEBHOOK and "config" in ret:
            config = ret["config"]
            if "secret" in config:
                config["secret"] = "********"  # Masked secret
                config["secret_configured"] = True
        return ret


class NotificationPolicySerializer(serializers.ModelSerializer):
    """
    Serializer for NotificationPolicy model. Validates event types and project active status.
    """

    class Meta:
        model = NotificationPolicy
        fields = [
            "id",
            "project",
            "channel",
            "severity",
            "event_types",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        from apps.incidents.models import IncidentEvent

        project = attrs.get("project") or (self.instance.project if self.instance else None)
        channel = attrs.get("channel") or (self.instance.channel if self.instance else None)
        severity = attrs.get("severity") or (self.instance.severity if self.instance else None)
        event_types = attrs.get("event_types") or (
            self.instance.event_types if self.instance else []
        )

        if channel and project and channel.project_id != project.id:
            raise DRFValidationError(
                {"channel": "Channel must belong to the same project as the policy."}
            )

        if project and (project.is_deleted or project.status != "active"):
            raise DRFValidationError(
                {"project": "Cannot create or update a policy for an inactive or deleted project."}
            )

        if project and channel and severity:
            policy_qs = NotificationPolicy.objects.filter(
                project=project,
                channel=channel,
                severity=severity,
            )
            if self.instance:
                policy_qs = policy_qs.exclude(pk=self.instance.pk)
            if policy_qs.exists():
                raise DRFValidationError(
                    {
                        "non_field_errors": [
                            "A policy for this channel and severity already exists on this project."
                        ]
                    }
                )

        valid_events = {
            IncidentEvent.EventType.CREATED,
            IncidentEvent.EventType.ASSIGNED,
            IncidentEvent.EventType.ACKNOWLEDGED,
            IncidentEvent.EventType.NOTE_ADDED,
            IncidentEvent.EventType.AUTO_RESOLVED,
            IncidentEvent.EventType.MANUALLY_RESOLVED,
            IncidentEvent.EventType.REOPENED,
        }

        if not isinstance(event_types, list):
            raise DRFValidationError({"event_types": "Must be a list of event types."})

        for evt in event_types:
            if evt not in valid_events:
                raise DRFValidationError({"event_types": f"Invalid event type: {evt}"})

        return attrs


class InAppNotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for InAppNotification model. Read-only.
    """

    incident_id = serializers.IntegerField(
        source="incident_event.incident_id", read_only=True, allow_null=True
    )
    event_type = serializers.CharField(
        source="incident_event.event_type", read_only=True, allow_null=True
    )
    incident_severity = serializers.CharField(
        source="incident_event.incident.severity", read_only=True, allow_null=True
    )
    project_name = serializers.CharField(
        source="incident_event.incident.project.name", read_only=True, allow_null=True
    )
    job_name = serializers.CharField(
        source="incident_event.incident.job.name", read_only=True, allow_null=True
    )

    class Meta:
        model = InAppNotification
        fields = [
            "id",
            "recipient",
            "incident_event",
            "incident_id",
            "event_type",
            "incident_severity",
            "project_name",
            "job_name",
            "title",
            "message",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields
