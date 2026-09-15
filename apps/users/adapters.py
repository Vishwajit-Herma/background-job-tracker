import logging
from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect

logger = logging.getLogger(__name__)
User = get_user_model()


class CustomAccountAdapter(DefaultAccountAdapter):
    def get_email_confirmation_url(self, request, emailconfirmation):
        return f"{settings.FRONTEND_URL}/verify-email/{emailconfirmation.key}"

    def send_mail(self, template_prefix, email, context):
        """Send email with graceful error handling so SMTP failures do not crash registration."""
        try:
            super().send_mail(template_prefix, email, context)
        except Exception as e:
            logger.error("Failed to send email to %s: %s", email, e)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Social account adapter enforcing strict security semantics:
    1. Only links accounts if the provider explicitly verifies email ownership.
    2. Preserves existing local users, passwords, teams, and permissions without modification.
    3. Prevents newly created social users from gaining staff or superuser privileges.
    4. Redirects gracefully on authentication errors rather than rendering default templates.
    """

    def pre_social_login(self, request, sociallogin):
        """
        Invoked after provider authentication but before login/signup completion.
        Controls secure account linking with verified identity matching.
        """
        # If the social account is already attached to an existing user, allow standard login
        if sociallogin.is_existing:
            return

        extra_data = sociallogin.account.extra_data or {}
        extra_email = extra_data.get("email")
        google_verified = bool(extra_data.get("email_verified") or extra_data.get("verified_email"))

        verified_emails = [
            e.email.lower() for e in sociallogin.email_addresses if e.verified and e.email
        ]

        candidate_email = extra_email or (
            sociallogin.email_addresses[0].email if sociallogin.email_addresses else None
        )
        if not candidate_email:
            return

        candidate_email_lower = candidate_email.strip().lower()
        is_verified = google_verified or (candidate_email_lower in verified_emails)

        # Case-insensitive check for existing local user
        existing_user = User.objects.filter(email__iexact=candidate_email_lower).first()
        if existing_user:
            # Reject account linking if Google identity does not confirm email verification
            if not is_verified:
                logger.warning(
                    "Security rejection: Social login attempted with unverified email %s for existing user %s",
                    candidate_email,
                    existing_user.pk,
                )
                raise ImmediateHttpResponse(
                    HttpResponseBadRequest(
                        "Cannot link account: The Google email is not verified by Google."
                    )
                )

            logger.info(
                "Linking verified Google account to existing user %s (%s)",
                existing_user.pk,
                existing_user.email,
            )
            # Connect the social account to the existing user row
            sociallogin.connect(request, existing_user)

            # Ensure the primary EmailAddress record for the existing user is marked verified
            email_obj = EmailAddress.objects.filter(
                user=existing_user, email__iexact=existing_user.email
            ).first()
            if email_obj:
                if not email_obj.verified:
                    email_obj.verified = True
                    email_obj.save(update_fields=["verified"])
            else:
                EmailAddress.objects.create(
                    user=existing_user,
                    email=existing_user.email,
                    verified=True,
                    primary=True,
                )

    def save_user(self, request, sociallogin, form=None):
        """
        Saves newly registered social user and ensures administrative privileges are never granted.
        """
        user = super().save_user(request, sociallogin, form=form)
        if user.is_staff or user.is_superuser:
            user.is_staff = False
            user.is_superuser = False
            user.save(update_fields=["is_staff", "is_superuser"])
        return user

    def on_authentication_error(
        self, request, provider, error=None, exception=None, extra_context=None
    ):
        """
        Redirect to frontend login page with error state rather than rendering unstyled error template.
        """
        logger.warning(
            "Social authentication error for provider %s: error=%s, exception=%s",
            getattr(provider, "id", provider),
            error,
            exception,
        )
        raise ImmediateHttpResponse(redirect(f"{settings.FRONTEND_URL}/login?error=oauth_error"))
