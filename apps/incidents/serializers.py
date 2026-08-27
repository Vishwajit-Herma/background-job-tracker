from rest_framework import serializers
from .models import Incident, IncidentEvent, IncidentNote, IncidentIntelligence


class IncidentEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = IncidentEvent
        fields = [
            "id",
            "event_type",
            "actor",
            "actor_name",
            "event_time",
            "metadata",
        ]
        read_only_fields = fields

    def get_actor_name(self, obj):
        if obj.actor:
            return obj.actor.get_full_name() or obj.actor.email
        if obj.metadata:
            return (
                obj.metadata.get("resolved_by_name")
                or obj.metadata.get("acknowledged_by_name")
                or obj.metadata.get("reopened_by_name")
                or ("System" if obj.event_type in ["CREATED", "AUTO_RESOLVED"] else None)
            )
        return "System" if obj.event_type in ["CREATED", "AUTO_RESOLVED"] else None


class IncidentNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.get_full_name", read_only=True)

    class Meta:
        model = IncidentNote
        fields = [
            "id",
            "incident",
            "author",
            "author_name",
            "content",
            "created_at",
        ]
        read_only_fields = ["id", "incident", "author", "author_name", "created_at"]


class IncidentSerializer(serializers.ModelSerializer):
    assigned_to_user_id = serializers.IntegerField(
        source="assigned_to.user_id", read_only=True, allow_null=True
    )
    assigned_to_name = serializers.SerializerMethodField()

    def get_assigned_to_name(self, obj):
        if obj.assigned_to and obj.assigned_to.user:
            return obj.assigned_to.user.get_full_name() or obj.assigned_to.user.email
        return None

    class Meta:
        model = Incident
        fields = [
            "id",
            "project",
            "job",
            "alert_rule",
            "status",
            "severity",
            "assigned_to",
            "assigned_to_user_id",
            "assigned_to_name",
            "assigned_at",
            "assigned_by",
            "acknowledged_at",
            "acknowledged_by",
            "resolved_at",
            "resolution_type",
            "resolved_by",
            "trigger_metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class IncidentAssignSerializer(serializers.Serializer):
    member_id = serializers.IntegerField(required=True)

    def validate_member_id(self, value):
        # Validation happens in the view against the project's team
        return value


class IncidentIntelligenceSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = IncidentIntelligence
        fields = [
            "id",
            "incident",
            "status",
            "impact",
            "correlations",
            "probable_causes",
            "analysis_window_start",
            "analysis_window_end",
            "analysis_version",
            "calculated_at",
        ]
        read_only_fields = fields

    def get_status(self, obj):
        return "READY"


class IncidentIntelligencePendingSerializer(serializers.Serializer):
    status = serializers.CharField(default="PENDING")
    message = serializers.CharField(default="Incident intelligence calculation is in progress.")
    incident_id = serializers.IntegerField()
    impact = serializers.DictField(allow_null=True, default=None)
    correlations = serializers.ListField(default=list)
    probable_causes = serializers.ListField(default=list)
    analysis_window_start = serializers.DateTimeField(allow_null=True, default=None)
    analysis_window_end = serializers.DateTimeField(allow_null=True, default=None)
    analysis_version = serializers.CharField(default="1.0")
    calculated_at = serializers.DateTimeField(allow_null=True, default=None)
