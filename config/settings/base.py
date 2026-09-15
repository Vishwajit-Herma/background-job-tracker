"""
Base settings for Background Job Tracker project.
"""

from pathlib import Path
import ssl

import environ

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Environment variables
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    DJANGO_SECRET_KEY=(str, "django-insecure-dev-key-change-in-production"),
    DATABASE_URL=(str, "sqlite:///db.sqlite3"),
)

# Read .env file if it exists
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# Application definition
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "drf_spectacular",
    "django_filters",
    "corsheaders",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "dj_rest_auth",
    "dj_rest_auth.registration",
    "django_celery_beat",
    "django_celery_results",
    "django_prometheus",
    "waffle",
    "django_extensions",
    "django_alive",
    "anymail",
    "channels",
]

LOCAL_APPS = [
    "apps.core",
    "apps.users",
    "apps.api",
    "apps.teams",
    "apps.config_management",
    "apps.projects",
    "apps.jobs",
    "apps.executions",
    "apps.alerts",
    "apps.incidents",
    "apps.notifications",
    "apps.reliability",
    "apps.ai",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "apps.users.impersonation.ImpersonationMiddleware",
    "waffle.middleware.WaffleMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # "apps.core.middleware.RequestTimingMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.users.impersonation.impersonation_context",
                "apps.core.feature_flags.get_feature_flags_for_template",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# Database
DATABASES = {
    "default": env.db("DATABASE_URL"),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)

# Custom user model
AUTH_USER_MODEL = "users.User"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Cache
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://127.0.0.1:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": "background_job_tracker",
    }
}

# Session - Persist sessions directly in PostgreSQL to save Redis command quotas
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Channel Layers (Django Channels)
REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "apps.core.realtime.channel_layer.LowCommandRedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}


# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# django-allauth
SITE_ID = 1
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = env("ACCOUNT_EMAIL_VERIFICATION", default="mandatory")
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_SUBJECT_PREFIX = ""


# Django REST Framework
from typing import Any

REST_FRAMEWORK: dict[str, Any] = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.config_management.pagination.Pagination",
    "PAGE_SIZE": 15,
    "EXCEPTION_HANDLER": "apps.config_management.responses.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "ai_investigate": "20/min",
    },
}

# drf-spectacular
SPECTACULAR_SETTINGS = {
    "TITLE": "Background Job Tracker API",
    "DESCRIPTION": "A Django Project to track Background jobs.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/",
}

# CORS
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://127.0.0.1:3000"],
)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=["http://localhost:3000", "http://127.0.0.1:3000"],
)


# Celery
from celery.schedules import crontab

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
if CELERY_BROKER_URL.startswith("rediss://"):
    CELERY_BROKER_USE_SSL = {
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
    }
else:
    CELERY_BROKER_USE_SSL = None
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": 3600,
    "polling_interval": 30,
    "health_check_interval": 600,
    "socket_keepalive": True,
    "socket_timeout": 45,
    "socket_connect_timeout": 30,
}
CELERY_RESULT_BACKEND = "django-db"
CELERY_RESULT_EXPIRES = 60 * 60 * 24 * 7  # 7 days (prevents django_celery_results unbounded growth)
CELERY_CACHE_BACKEND = "django-cache"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_WORKER_SEND_TASK_EVENTS = False
CELERY_SEND_EVENTS = False
CELERY_WORKER_ENABLE_REMOTE_CONTROL = False

CELERY_BEAT_SCHEDULE = {
    "hard-delete-soft-deleted-records": {
        "task": "config_management.hard_delete_soft_deleted_records",
        "schedule": crontab(hour=0, minute=0),  # Runs every day at midnight
    },
    "evaluate-alert-rules": {
        "task": "alerts.evaluate_alert_rules",
        "schedule": crontab(minute="*/15"),  # Runs every 15 minutes
        "options": {"expires": 900},
    },
    "recover-orphaned-deliveries": {
        "task": "notifications.recover_orphaned_deliveries",
        "schedule": crontab(minute="*/15"),  # Runs every 15 minutes
        "options": {"expires": 900},
    },
    "evaluate-job-reliability": {
        "task": "reliability.evaluate_reliability",
        "schedule": crontab(minute="*/15"),  # Runs every 15 minutes
        "options": {"expires": 900},
    },
    "recalculate-job-baselines": {
        "task": "reliability.recalculate_baselines",
        "schedule": crontab(hour="*/6", minute=0),  # Runs every 6 hours
    },
    "prune-old-executions": {
        "task": "executions.prune_old_executions",
        "schedule": crontab(hour=2, minute=0),  # Runs daily at 2:00 AM UTC
    },
    "celery-backend-cleanup": {
        "task": "celery.backend_cleanup",
        "schedule": crontab(hour=4, minute=0),  # Runs daily at 4:00 AM UTC
    },
    "clear-expired-sessions": {
        "task": "config_management.clear_expired_sessions",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Runs every Sunday at 3:00 AM UTC
    },
}

# Execution Telemetry Retention
EXECUTIONS_RETENTION_DAYS = env.int("EXECUTIONS_RETENTION_DAYS", default=30)
EXECUTIONS_PURGE_BATCH_SIZE = env.int("EXECUTIONS_PURGE_BATCH_SIZE", default=5000)


# Email
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="background_job_tracker@example.com")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose" if DEBUG else "json",
        },
    },
    "root": {
        "level": env("LOG_LEVEL", default="INFO"),
        "handlers": ["console"],
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Site Configuration
SITE_NAME = env("SITE_NAME", default="Background Job Tracker")
SITE_URL = env("SITE_URL", default="http://localhost:8000")
SUPPORT_EMAIL = env("SUPPORT_EMAIL", default=DEFAULT_FROM_EMAIL)

# dj-rest-auth Configuration
REST_AUTH = {
    "SESSION_LOGIN": True,
    "USE_JWT": False,
    "TOKEN_MODEL": None,
    "TOKEN_SERIALIZER": "apps.api.serializers.DummyTokenSerializer",
    "REGISTER_SERIALIZER": "apps.api.serializers.CustomRegisterSerializer",
    "USER_DETAILS_SERIALIZER": "apps.api.serializers.CustomUserDetailsSerializer",
}

# Frontend URLs
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")

ACCOUNT_ADAPTER = "apps.users.adapters.CustomAccountAdapter"
SOCIALACCOUNT_ADAPTER = "apps.users.adapters.CustomSocialAccountAdapter"

# Google OAuth Configuration
GOOGLE_CLIENT_ID = env.str("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = env.str("GOOGLE_CLIENT_SECRET", default="")

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": [
            {
                "client_id": GOOGLE_CLIENT_ID,
                "secret": GOOGLE_CLIENT_SECRET,
                "key": "",
            },
        ],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "VERIFIED_EMAIL": False,
    },
}
SOCIALACCOUNT_LOGIN_ON_GET = True
LOGIN_REDIRECT_URL = FRONTEND_URL
LOGOUT_REDIRECT_URL = FRONTEND_URL
USE_X_FORWARDED_HOST = True

# AI Reliability Assistant (Gemini)
GEMINI_API_KEY = env.str("GEMINI_API_KEY", default="")
GEMINI_MODEL = env.str("GEMINI_MODEL", default="gemini-3.8-flash")
GEMINI_FALLBACK_MODELS = env.list(
    "GEMINI_FALLBACK_MODELS",
    default=[
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ],
)
# Cooldown duration in seconds when a model returns 429/quota exhausted (default: 1 hour)
GEMINI_COOLDOWN_SECONDS = env.int("GEMINI_COOLDOWN_SECONDS", default=3600)
# Short cooldown in seconds when a model returns 503 high demand (default: 60 seconds)
GEMINI_DEMAND_COOLDOWN_SECONDS = env.int("GEMINI_DEMAND_COOLDOWN_SECONDS", default=60)
# Models with thinking/large contexts can take 30-90s
# Override with GEMINI_TIMEOUT env var if needed.
GEMINI_TIMEOUT = env.int("GEMINI_TIMEOUT", default=60)

# Team Management
# Maximum active teams a regular user can create/own.
# None, blank/empty string, or <= 0 means unlimited.
MAX_TEAMS_PER_USER = env("MAX_TEAMS_PER_USER", default=3)
