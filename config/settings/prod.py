"""Production settings."""

from .base import *  # noqa: F403, F401

DEBUG = False

# Security settings
SECURE_SSL_REDIRECT = True  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)  # noqa: F405
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=True)  # noqa: F405
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# Session security
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# CSRF security
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"


# Database connection pooling
# ATOMIC_REQUESTS is disabled in production: it wraps every request in a
# transaction which prevents CONN_MAX_AGE from reusing persistent connections.
# Django cannot return a connection mid-transaction, so every request would pay
# the full TCP + TLS + Postgres auth overhead. Individual services use
# @transaction.atomic() explicitly where needed.
DATABASES["default"]["ATOMIC_REQUESTS"] = False  # noqa: F405
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=600)  # noqa: F405

# Logging - JSON format for production
LOGGING = {  # noqa: F405
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "level": env("LOG_LEVEL", default="INFO"),  # noqa: F405
        "handlers": ["console"],
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


# Email configuration - Brevo / Resend (Anymail) if API key is present, SMTP fallback if EMAIL_HOST set, else Logging backend
BREVO_API_KEY = env("BREVO_API_KEY", default="")  # noqa: F405
RESEND_API_KEY = env("RESEND_API_KEY", default="")  # noqa: F405
EMAIL_HOST = env("EMAIL_HOST", default="")  # noqa: F405

if BREVO_API_KEY:
    EMAIL_BACKEND = env("EMAIL_BACKEND", default="anymail.backends.brevo.EmailBackend")  # noqa: F405
    ANYMAIL = {
        "BREVO_API_KEY": BREVO_API_KEY,
    }
elif RESEND_API_KEY:
    EMAIL_BACKEND = env("EMAIL_BACKEND", default="anymail.backends.resend.EmailBackend")  # noqa: F405
    ANYMAIL = {
        "RESEND_API_KEY": RESEND_API_KEY,
    }
elif EMAIL_HOST:
    EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")  # noqa: F405
    EMAIL_PORT = env.int("EMAIL_PORT", default=587)  # noqa: F405
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")  # noqa: F405
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")  # noqa: F405
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)  # noqa: F405
else:
    EMAIL_BACKEND = env("EMAIL_BACKEND", default="apps.users.mail_backends.LoggingEmailBackend")  # noqa: F405

# Frontend & Site URLs
FRONTEND_URL = env("FRONTEND_URL", default="https://background-job-tracker-wine.vercel.app")  # noqa: F405
SITE_URL = env("SITE_URL", default=FRONTEND_URL)  # noqa: F405

# Admin
ADMINS = [
    ("Vishwajit Herma", "vishuherma@gmail.com"),
]
MANAGERS = ADMINS
