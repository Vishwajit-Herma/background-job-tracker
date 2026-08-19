"""
WSGI config for Background Job Tracker project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_wsgi_application()

# Setup signal handlers for graceful shutdown
from config.signal_handlers import setup_signal_handlers

setup_signal_handlers()
