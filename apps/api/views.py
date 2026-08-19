"""API views."""

from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def api_root(request):
    """API root endpoint."""
    return Response(
        {
            "message": "Welcome to Background Job Tracker API",
            "version": "1.0.0",
        }
    )
