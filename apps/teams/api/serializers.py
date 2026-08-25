from django.utils.text import slugify
from rest_framework import serializers

from apps.api.serializers import CustomUserDetailsSerializer
from apps.teams.models import Team, TeamMember, TeamInvitation


class TeamMemberSerializer(serializers.ModelSerializer):
    """Serializer for TeamMember."""

    user = CustomUserDetailsSerializer(read_only=True)

    class Meta:
        model = TeamMember
        fields = ["id", "team", "user", "role", "is_active", "joined_at"]
        read_only_fields = ["id", "team", "user", "is_active", "joined_at"]


class TeamSerializer(serializers.ModelSerializer):
    """Serializer for Team."""
    
    slug = serializers.SlugField(required=False)

    class Meta:
        model = Team
        fields = ["id", "name", "slug", "description", "owner", "created_at", "updated_at"]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    def validate(self, attrs):
        if not attrs.get("slug") and attrs.get("name"):
            attrs["slug"] = slugify(attrs["name"])
        return attrs


class TeamMemberUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a TeamMember (role change)."""

    class Meta:
        model = TeamMember
        fields = ["role"]


class TeamInvitationSerializer(serializers.ModelSerializer):
    """Serializer for TeamInvitation."""

    invited_by_email = serializers.EmailField(source="invited_by.email", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)

    class Meta:
        model = TeamInvitation
        fields = ["id", "team", "team_name", "email", "role", "status", "invited_by", "invited_by_email", "created_at", "expires_at"]
        read_only_fields = ["id", "team", "team_name", "status", "invited_by", "invited_by_email", "created_at", "expires_at"]
