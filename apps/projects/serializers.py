from rest_framework import serializers
from .models import Project, APIKey


class ProjectSerializer(serializers.ModelSerializer):
    jobs_count = serializers.IntegerField(read_only=True, required=False)
    executions_count = serializers.IntegerField(read_only=True, required=False)
    success_rate = serializers.SerializerMethodField()
    active_incidents_count = serializers.IntegerField(read_only=True, required=False)
    operational_status = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "team",
            "name",
            "description",
            "status",
            "created_at",
            "updated_at",
            "created_by",
            "modified_by",
            "jobs_count",
            "executions_count",
            "success_rate",
            "active_incidents_count",
            "operational_status",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "modified_by",
            "jobs_count",
            "executions_count",
            "active_incidents_count",
        ]

    def get_fields(self):
        """Make 'team' read-only on update to prevent tenant-hopping."""
        fields = super().get_fields()
        if self.instance:
            fields["team"].read_only = True
        return fields

    def get_success_rate(self, obj):
        executions = getattr(obj, "executions_count", 0)
        if not executions:
            return None
        successes = getattr(obj, "success_count", 0)
        return round((successes / executions) * 100, 2)

    def get_operational_status(self, obj):
        if getattr(obj, "has_critical_incident", False):
            return "CRITICAL"
        if getattr(obj, "active_incidents_count", 0) > 0:
            return "DEGRADED"
        return "HEALTHY"

    def validate(self, attrs):
        """Ensure unique active project names per team."""
        team = self.instance.team if self.instance else attrs.get("team")
        name = attrs.get("name", self.instance.name if self.instance else None)

        if self.instance and self.instance.is_deleted and "status" in attrs:
            raise serializers.ValidationError(
                {"status": "Cannot change status of a deleted project."}
            )

        if name and team:
            qs = Project.objects.filter(team=team, name=name)
            # If updating, exclude the current instance
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise serializers.ValidationError(
                    {"name": "An active project with this name already exists in this team."}
                )
        return attrs

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if getattr(instance, "is_deleted", False):
            ret["status"] = "deleted"
        return ret


class APIKeySerializer(serializers.ModelSerializer):
    """
    Read-only serializer for listing and retrieving API keys.
    Does NOT include the raw key or the hash.
    """

    class Meta:
        model = APIKey
        fields = [
            "id",
            "name",
            "key_prefix",
            "is_revoked",
            "created_at",
            "created_by",
            "revoked_at",
            "revoked_by",
        ]
        read_only_fields = fields


class APIKeyCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating an API key.
    It expects `name` and securely generates the key internally.
    """

    key = serializers.CharField(read_only=True)

    class Meta:
        model = APIKey
        fields = ["id", "name", "key", "key_prefix", "created_at", "created_by"]
        read_only_fields = ["id", "key_prefix", "created_at", "created_by"]

    def validate(self, attrs):
        project = self.context["project"]
        if project.status != "active":
            raise serializers.ValidationError("Cannot create API keys for inactive projects.")

        name = attrs.get("name")
        if APIKey.objects.filter(project=project, name=name, is_deleted=False).exists():
            raise serializers.ValidationError(
                {"name": "An active API key with this name already exists in this project."}
            )

        return attrs

    def create(self, validated_data):
        project = self.context["project"]
        user = self.context["request"].user

        # Create key securely via model classmethod
        instance, raw_key = APIKey.create_key(project, validated_data["name"], user)

        # We manually attach the raw key to the instance so the serializer can return it once.
        # This attribute is not saved to the DB.
        instance.key = raw_key
        return instance
