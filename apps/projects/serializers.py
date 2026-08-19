from rest_framework import serializers
from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "id",
            "team",
            "name",
            "description",
            "created_at",
            "updated_at",
            "created_by",
            "modified_by",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "modified_by",
        ]

    def get_fields(self):
        """Make 'team' read-only on update to prevent tenant-hopping."""
        fields = super().get_fields()
        if self.instance:
            fields["team"].read_only = True
        return fields

    def validate(self, attrs):
        """Ensure unique active project names per team."""
        team = self.instance.team if self.instance else attrs.get("team")
        name = attrs.get("name", self.instance.name if self.instance else None)

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
