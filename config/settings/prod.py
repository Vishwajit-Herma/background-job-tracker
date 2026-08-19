"""Production settings."""

from .base import *  # noqa: F403, F401

DEBUG = False

# Security settings
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
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
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"


# Database connection pooling
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


# OpenTelemetry
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor


# Set up tracer provider
tracer_provider = TracerProvider()
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

# Configure OTLP exporter
otlp_exporter = OTLPSpanExporter(
    endpoint=env("OTEL_EXPORTER_OTLP_ENDPOINT", default="http://localhost:4317"),  # noqa: F405
)
span_processor = BatchSpanProcessor(otlp_exporter)
tracer_provider.add_span_processor(span_processor)

# Auto-instrument
DjangoInstrumentor().instrument()
PsycopgInstrumentor().instrument()
CeleryInstrumentor().instrument()


# Email - SMTP by default, configured via environment
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")  # noqa: F405
EMAIL_HOST = env("EMAIL_HOST", default="localhost")  # noqa: F405
EMAIL_PORT = env.int("EMAIL_PORT", default=587)  # noqa: F405
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")  # noqa: F405
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")  # noqa: F405
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)  # noqa: F405

# Admin
ADMINS = [
    ("Vishwajit Herma", "vishuherma@gmail.com"),
]
MANAGERS = ADMINS
