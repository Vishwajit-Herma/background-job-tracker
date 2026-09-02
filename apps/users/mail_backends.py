import sys
from django.core.mail.backends.base import BaseEmailBackend


class LoggingEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        msg_count = 0
        for message in email_messages:
            print("========== EMAIL GENERATED ==========")
            print(f"To: {', '.join(message.to)}")
            print(f"Subject: {message.subject}")
            print(f"Body:\n{message.body}")
            print("=====================================")
            sys.stdout.flush()
            msg_count += 1
        return msg_count
