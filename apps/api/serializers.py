from django.contrib.auth import get_user_model
from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import UserDetailsSerializer
from rest_framework import serializers

User = get_user_model()


class CustomRegisterSerializer(RegisterSerializer):
    username = None

    def validate_email(self, email):
        email = super().validate_email(email)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        return email


class DummyTokenSerializer(serializers.Serializer):
    pass


class CustomUserDetailsSerializer(UserDetailsSerializer):
    avatar_url = serializers.ReadOnlyField()

    class Meta(UserDetailsSerializer.Meta):
        fields = UserDetailsSerializer.Meta.fields + ("is_staff", "avatar_url")
