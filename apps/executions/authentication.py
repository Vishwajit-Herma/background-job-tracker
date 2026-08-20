from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed

from apps.projects.models import APIKey


class ProjectAPIKeyAuthentication(authentication.BaseAuthentication):
    """
    Authenticates an SDK client using the X-API-Key header.
    Validates the key against the hashed APIKey model and returns the
    associated Project as the `request.auth` object.
    """

    def authenticate(self, request):
        api_key = request.META.get("HTTP_X_API_KEY")
        if not api_key:
            return None

        # Expected format: rk_live_...
        if not api_key.startswith("rk_live_"):
            raise AuthenticationFailed("Invalid API Key format.")

        key_prefix = api_key[:12]

        try:
            # We select_related project to avoid N+1 downstream
            key_record = APIKey.objects.select_related("project").get(
                key_prefix=key_prefix, is_deleted=False
            )
        except APIKey.DoesNotExist as err:
            raise AuthenticationFailed("Invalid API Key.") from err

        if key_record.is_revoked:
            raise AuthenticationFailed("API Key has been revoked.")

        if not key_record.verify_key(api_key):
            raise AuthenticationFailed("Invalid API Key.")

        project = key_record.project

        if project.is_deleted:
            raise AuthenticationFailed("Invalid API Key.")  # Pretend it doesn't exist or is invalid

        # We return (user, auth)
        # Since this is a machine-to-machine request, there is no user.
        return (None, project)

    def authenticate_header(self, request):
        return "X-API-Key"
