"""Core views."""

from django.db import connection
from django.http import JsonResponse

from django.core.cache import cache


def index(request):
    """Home page."""
    return JsonResponse(
        {
            "message": "Welcome to Background Job Tracker",
            "version": "1.0.0",
        }
    )


def health_check(request):
    """Health check endpoint."""
    return JsonResponse({"status": "healthy"})


def readiness_check(request):
    """Readiness check with database and cache verification."""
    checks = {"database": False, "cache": False}

    try:
        # Check database
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = True
    except Exception:
        pass

    try:
        # Check cache
        cache.set("health_check", "ok", 10)
        checks["cache"] = cache.get("health_check") == "ok"
    except Exception:
        pass

    all_ready = all(checks.values())
    status_code = 200 if all_ready else 503

    return JsonResponse({"ready": all_ready, "checks": checks}, status=status_code)
