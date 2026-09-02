"""API views."""

import logging
import urllib.parse

from allauth.account import app_settings
from allauth.account.models import EmailAddress, get_emailconfirmation_model
from django.contrib.auth import get_user_model
from django.core import signing
from django.utils.translation import gettext_lazy as _
from dj_rest_auth.registration.serializers import (
    ResendEmailVerificationSerializer,
    VerifyEmailSerializer,
)
from rest_framework import permissions, status
from rest_framework.decorators import api_view
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(["GET"])
def api_root(request):
    """API root endpoint."""
    return Response(
        {
            "message": "Welcome to Background Job Tracker API",
            "version": "1.0.0",
        }
    )


class CustomResendEmailVerificationView(CreateAPIView):
    """
    Robust Resend Email Verification view with case-insensitive matching and fallback.
    """

    permission_classes = (permissions.AllowAny,)
    serializer_class = ResendEmailVerificationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_email = serializer.validated_data.get("email", "").strip().lower()
        if not raw_email:
            return Response({"detail": _("ok")}, status=status.HTTP_200_OK)

        email_obj = EmailAddress.objects.filter(email__iexact=raw_email).first()

        # If EmailAddress record is missing but User exists, link/create it
        if not email_obj:
            user = User.objects.filter(email__iexact=raw_email).first()
            if user:
                email_obj = EmailAddress.objects.create(
                    user=user,
                    email=user.email,
                    primary=True,
                    verified=False,
                )

        if email_obj:
            if not email_obj.verified:
                logger.info("Resending confirmation email to %s", email_obj.email)
                email_obj.send_confirmation(request)
            else:
                logger.info("Email %s is already verified, skipping resend.", email_obj.email)
        else:
            logger.warning("Resend requested for non-existent email: %s", raw_email)

        return Response({"detail": _("ok")}, status=status.HTTP_200_OK)


class CustomVerifyEmailView(CreateAPIView):
    """
    Robust Email Verification view that handles URL decoding and already-verified status gracefully.
    """

    permission_classes = (permissions.AllowAny,)
    serializer_class = VerifyEmailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_key = serializer.validated_data.get("key", "").strip()
        key = urllib.parse.unquote(raw_key)

        model = get_emailconfirmation_model()
        confirmation = model.from_key(key)

        if not confirmation:
            # Check if this key belongs to an already-verified email address
            try:
                max_age = 60 * 60 * 24 * app_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS
                pk = signing.loads(key, max_age=max_age, salt=app_settings.SALT)
                email_obj = EmailAddress.objects.filter(pk=pk).first()
                if email_obj and email_obj.verified:
                    return Response(
                        {"detail": _("Email is already verified.")}, status=status.HTTP_200_OK
                    )
            except Exception:
                pass

            return Response(
                {"detail": _("This verification link is invalid or has expired.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        confirmation.confirm(request)
        return Response({"detail": _("Email successfully verified.")}, status=status.HTTP_200_OK)
