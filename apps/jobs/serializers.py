from django.utils import timezone
from rest_framework import serializers

from apps.projects.models import Project
from .models import Job, TaskRegistry


class JobSerializer(serializers.ModelSerializer):
    """
    Standard serializer for retrieving and listing Jobs.
    """

    # Expose is_deleted explicitly as requested by the story for deleted state
    is_deleted = serializers.BooleanField(read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "project",
            "name",
            "task_identifier",
            "description",
            "status",
            "verification_status",
            "last_verified_at",
            "is_deleted",
            "created_at",
            "updated_at",
            "created_by",
            "modified_by",
        ]
        read_only_fields = [
            "id",
            "verification_status",
            "last_verified_at",
            "created_at",
            "updated_at",
            "created_by",
            "modified_by",
            "is_deleted",
        ]


class JobCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for manually creating a Job.
    """

    class Meta:
        model = Job
        fields = [
            "id",
            "project",
            "name",
            "task_identifier",
            "description",
            "status",
            "verification_status",
            "last_verified_at",
            "created_at",
            "updated_at",
            "created_by",
            "modified_by",
        ]
        read_only_fields = [
            "id",
            "verification_status",
            "last_verified_at",
            "created_at",
            "updated_at",
            "created_by",
            "modified_by",
        ]
        extra_kwargs = {
            "name": {"required": True, "allow_blank": False},
            "task_identifier": {"required": True, "allow_blank": False},
        }

    def validate(self, attrs):
        project = attrs.get("project")

        if project.is_deleted:
            raise serializers.ValidationError("Cannot create Jobs for a deleted project.")

        if project.status != Project.Status.ACTIVE:
            raise serializers.ValidationError("Cannot create Jobs for an inactive project.")

        task_identifier = attrs.get("task_identifier")

        # Duplicate project + task_identifier check for active jobs
        if Job.objects.filter(
            project=project, task_identifier=task_identifier, is_deleted=False
        ).exists():
            raise serializers.ValidationError(
                {
                    "task_identifier": "An active Job with this task identifier already exists in this project."
                }
            )

        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        project = validated_data["project"]
        task_identifier = validated_data["task_identifier"]

        # Determine initial verification status based on the TaskRegistry
        in_registry = TaskRegistry.objects.filter(
            project=project, task_identifier=task_identifier
        ).exists()
        if in_registry:
            validated_data["verification_status"] = Job.VerificationStatus.VERIFIED
            validated_data["last_verified_at"] = timezone.now()
        else:
            validated_data["verification_status"] = Job.VerificationStatus.UNVERIFIED

        validated_data["created_by"] = user
        validated_data["modified_by"] = user

        return super().create(validated_data)


class JobUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating an existing Job.
    """

    class Meta:
        model = Job
        fields = [
            "id",
            "project",
            "name",
            "task_identifier",
            "description",
            "status",
            "verification_status",
            "last_verified_at",
            "created_at",
            "updated_at",
            "created_by",
            "modified_by",
        ]
        read_only_fields = [
            "id",
            "project",  # Project cannot be changed on update
            "task_identifier",  # Task identifier shouldn't be changed, it defines the job
            "verification_status",
            "last_verified_at",
            "created_at",
            "updated_at",
            "created_by",
            "modified_by",
        ]
        extra_kwargs = {
            "name": {"required": False, "allow_blank": False},
        }

    def validate(self, attrs):
        # Deleted job cannot have its status changed
        job = self.instance
        if job.is_deleted and "status" in attrs and attrs["status"] != job.status:
            raise serializers.ValidationError(
                {"status": "A deleted Job cannot have its status changed."}
            )

        return attrs

    def update(self, instance, validated_data):
        user = self.context["request"].user
        validated_data["modified_by"] = user
        return super().update(instance, validated_data)


class TaskRegistrySyncSerializer(serializers.Serializer):
    """
    Serializer for the SDK to push discovered task identifiers.
    Expects a list of string identifiers.
    """

    tasks = serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=False),
        allow_empty=False,
    )
