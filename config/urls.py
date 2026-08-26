"""URL configuration for Background Job Tracker project."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path

from django.shortcuts import redirect


def password_reset_redirect(request, uidb64, token):
    return redirect(f"{settings.FRONTEND_URL}/reset-password/{uidb64}/{token}")


urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/", admin.site.urls),
    # Health checks - django-alive provides standardized endpoints
    path("health/", include("django_alive.urls")),
    path(
        "password-reset/<uidb64>/<token>/", password_reset_redirect, name="password_reset_confirm"
    ),
    path("", include("apps.core.urls")),
    path("api/", include("apps.api.urls")),
    path("accounts/", include("allauth.urls")),
    path("users/", include("apps.users.urls")),
    path("teams/", include("apps.teams.urls")),
    path("", include("django_prometheus.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns.insert(0, path("__debug__/", include(debug_toolbar.urls)))
