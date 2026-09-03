from rest_framework import serializers
from .models import (
    Incident,
    IncidentEvent,
    IncidentNote,
    IncidentIntelligence,
    Runbook,
    IncidentRunbookExecution,
    IncidentPostmortem,
    PostmortemActionItem,
)


class IncidentEventSerializer(serializers.ModelSerializer):
    """
    Serializer for audit timeline events associated with an Incident.
    Includes resolution of human-readable actor names for users or system events.
    """

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
    """
    Serializer for investigation notes attached to an Incident.
    Captures immutable note content and author details.
    """

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
    """
    Serializer for Incident records, exposing status, severity, assignment,
    resolution metadata, and trigger condition context.
    """

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
    """
    Serializer for assigning or unassigning an Incident to a TeamMember.
    """

    member_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_member_id(self, value):
        # Validation happens in the view against the project's team
        return value


class IncidentIntelligenceSerializer(serializers.ModelSerializer):
    """
    Serializer for computed Incident Intelligence analysis (impact, correlations, probable root causes).
    """

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
    """
    Serializer for pending/async Incident Intelligence calculation responses (HTTP 202 Accepted).
    """

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


class RunbookSerializer(serializers.ModelSerializer):
    """
    Serializer for managing operational Runbooks.
    Includes match priority and reasoning attributes when scored for an incident.
    """

    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)
    updated_by_name = serializers.CharField(source="updated_by.get_full_name", read_only=True)
    trigger_type = serializers.ChoiceField(
        choices=Runbook.TriggerType.choices,
        allow_null=True,
        allow_blank=True,
        required=False,
    )
    match_priority = serializers.IntegerField(read_only=True, required=False)
    match_reason = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = Runbook
        fields = [
            "id",
            "project",
            "job",
            "name",
            "description",
            "trigger_type",
            "steps",
            "is_active",
            "match_priority",
            "match_reason",
            "created_by",
            "created_by_name",
            "updated_by",
            "updated_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "match_priority",
            "match_reason",
            "created_by",
            "created_by_name",
            "updated_by",
            "updated_by_name",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        # Validate that if job is provided, it belongs to the same project
        job = data.get("job")
        project = data.get("project")

        # In a partial update (PATCH), project or job might not be in data.
        # We need to fall back to the instance's values.
        if self.instance:
            project = project or self.instance.project
            job = job if "job" in data else self.instance.job

        if job and job.project_id != project.id:
            raise serializers.ValidationError(
                {"job": "The job must belong to the same project as the runbook."}
            )

        return data


class IncidentRunbookExecutionSerializer(serializers.ModelSerializer):
    """
    Serializer for tracking an active or past execution instance of a Runbook for an Incident.
    """

    runbook_name = serializers.CharField(source="runbook.name", read_only=True)
    runbook_details = RunbookSerializer(source="runbook", read_only=True)
    started_by_name = serializers.SerializerMethodField()

    class Meta:
        model = IncidentRunbookExecution
        fields = [
            "id",
            "incident",
            "runbook",
            "runbook_name",
            "runbook_details",
            "started_by",
            "started_by_name",
            "started_at",
            "completed_at",
            "step_states",
            "step_history",
            "status",
        ]
        read_only_fields = [
            "id",
            "runbook_name",
            "runbook_details",
            "started_by",
            "started_by_name",
            "started_at",
            "completed_at",
            "step_history",
        ]

    def get_started_by_name(self, obj):
        if obj.started_by:
            return obj.started_by.get_full_name() or obj.started_by.email
        return None


class PostmortemActionItemSerializer(serializers.ModelSerializer):
    """
    Serializer for action items (prevention tasks) created during postmortem analysis.
    """

    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = PostmortemActionItem
        fields = [
            "id",
            "postmortem",
            "title",
            "description",
            "status",
            "owner",
            "owner_name",
            "due_date",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "postmortem", "completed_at", "created_at", "updated_at"]

    def get_owner_name(self, obj):
        if obj.owner and obj.owner.user:
            return obj.owner.user.get_full_name() or obj.owner.user.email
        return None


class IncidentPostmortemSerializer(serializers.ModelSerializer):
    """
    Serializer for comprehensive Incident Postmortem reports and review status.
    """

    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)
    updated_by_name = serializers.CharField(source="updated_by.get_full_name", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.get_full_name", read_only=True)
    action_items = PostmortemActionItemSerializer(many=True, read_only=True)

    class Meta:
        model = IncidentPostmortem
        fields = [
            "id",
            "incident",
            "status",
            "summary",
            "impact_summary",
            "probable_cause",
            "confirmed_root_cause",
            "resolution",
            "contributing_factors",
            "timeline",
            "what_went_well",
            "what_went_wrong",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "action_items",
            "created_by",
            "created_by_name",
            "updated_by",
            "updated_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "incident",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "created_by",
            "created_by_name",
            "updated_by",
            "updated_by_name",
            "created_at",
            "updated_at",
        ]


class ExecuteRunbookSerializer(serializers.Serializer):
    """
    Serializer payload for launching execution of a specific Runbook.
    """

    runbook_id = serializers.IntegerField(required=True)


class TransitionStepSerializer(serializers.Serializer):
    """
    Serializer payload for transitioning state of an individual step in a Runbook execution.
    """

    execution_id = serializers.IntegerField(required=True)
    step_id = serializers.CharField(required=True)
    from_state = serializers.CharField(required=True)
    to_state = serializers.CharField(required=True)


class ActionItemCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new Postmortem action item.
    """

    class Meta:
        model = PostmortemActionItem
        fields = ["title", "description", "owner", "status", "due_date"]


class UpdateRunbookExecutionStatusSerializer(serializers.Serializer):
    """
    Serializer payload for updating the overall status of a Runbook execution.
    """

    status = serializers.ChoiceField(
        choices=["IN_PROGRESS", "COMPLETED", "CANCELLED"],
        required=True,
    )
