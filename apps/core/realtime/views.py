import secrets
from django.core.cache import cache
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

TICKET_TIMEOUT_SECONDS = 60
TICKET_PREFIX = "ws_ticket:"


class WebSocketTicketView(APIView):
    """
    Generate an ephemeral, single-use ticket for establishing an authenticated
    WebSocket connection across cross-origin deployments (Vercel to Render).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        ticket = secrets.token_urlsafe(32)
        key = f"{TICKET_PREFIX}{ticket}"
        # Store only the minimal identity required: user.id
        cache.set(key, request.user.id, timeout=TICKET_TIMEOUT_SECONDS)

        return Response(
            {
                "ticket": ticket,
                "expires_in": TICKET_TIMEOUT_SECONDS,
            },
            status=status.HTTP_200_OK,
        )
