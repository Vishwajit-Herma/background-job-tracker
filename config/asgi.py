"""ASGI config for Background Job Tracker project with Django Channels support."""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from apps.core.realtime.middleware import WebSocketTicketAuthMiddleware  # noqa: E402
from apps.core.realtime.routing import websocket_urlpatterns  # noqa: E402
from config.signal_handlers import setup_signal_handlers  # noqa: E402

setup_signal_handlers()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            WebSocketTicketAuthMiddleware(URLRouter(websocket_urlpatterns))
        ),
    }
)
