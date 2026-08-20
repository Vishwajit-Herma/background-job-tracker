"""
ASGI config for Background Job Tracker project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_asgi_application()

# Setup signal handlers for graceful shutdown
from config.signal_handlers import setup_signal_handlers

setup_signal_handlers()
