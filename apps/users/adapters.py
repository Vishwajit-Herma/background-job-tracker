import logging
from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings

logger = logging.getLogger(__name__)


class CustomAccountAdapter(DefaultAccountAdapter):
    def get_email_confirmation_url(self, request, emailconfirmation):
        return f"{settings.FRONTEND_URL}/verify-email/{emailconfirmation.key}"

    def send_mail(self, template_prefix, email, context):
        """Send email with graceful error handling so SMTP failures do not crash registration."""
        try:
            super().send_mail(template_prefix, email, context)
        except Exception as e:
            logger.error("Failed to send email to %s: %s", email, e)
