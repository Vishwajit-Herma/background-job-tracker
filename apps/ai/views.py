"""Views for AI Reliability Assistant."""

import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.ai.providers.base import (
    AIConfigurationError,
    AIProviderError,
    AIProviderTimeoutError,
    AIValidationError,
)
from apps.ai.serializers import (
    AIInvestigationRequestSerializer,
    AIInvestigationResponseSerializer,
)
from apps.ai.services import investigate_incident
from apps.config_management.responses import CustomResponse
from apps.config_management.views import CustomBaseAPIView
from apps.incidents.models import Incident
from apps.incidents.permissions import IncidentPermission

logger = logging.getLogger(__name__)


class IncidentAIInvestigateView(CustomBaseAPIView):
    """Investigate an incident using AI Reliability Assistant."""

    permission_classes = list(CustomBaseAPIView.permission_classes) + [IncidentPermission]  # type: ignore[operator]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai_investigate"

    def post(self, request, incident_id: int):
        # 1. Fetch incident
        incident = (
            Incident.objects.select_related("project__team", "job").filter(pk=incident_id).first()
        )
        if not incident:
            return Response(
                {"message": "Incident not found.", "error": "Not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 2. Enforce tenant object permissions
        self.check_object_permissions(request, incident)

        # 3. Validate request payload
        request_serializer = AIInvestigationRequestSerializer(data=request.data)
        if not request_serializer.is_valid():
            return Response(
                {
                    "errors": request_serializer.errors,
                    "message": "Invalid investigation request parameters.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        question = request_serializer.validated_data["question"]

        # 4. Perform investigation
        try:
            result = investigate_incident(incident=incident, question=question)
            response_serializer = AIInvestigationResponseSerializer(result)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except AIConfigurationError as err:
            logger.error("AI service configuration error for INC-%s: %s", incident_id, err)
            return CustomResponse.error(
                message="AI Reliability Assistant is not configured on this server.",
                errors={"code": "AI_CONFIGURATION_ERROR"},
                code=status.HTTP_503_SERVICE_UNAVAILABLE,
                error_code="AI_CONFIGURATION_ERROR",
            )
        except AIProviderTimeoutError as err:
            logger.warning("AI provider timed out for INC-%s: %s", incident_id, err)
            return CustomResponse.error(
                message="AI service request timed out. Please try again.",
                errors={"code": "AI_PROVIDER_TIMEOUT"},
                code=status.HTTP_504_GATEWAY_TIMEOUT,
                error_code="AI_PROVIDER_TIMEOUT",
            )
        except AIValidationError as err:
            logger.error("AI validation error for INC-%s: %s", incident_id, err)
            return CustomResponse.error(
                message="AI provider response failed schema validation.",
                errors={"code": "AI_VALIDATION_ERROR"},
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_code="AI_VALIDATION_ERROR",
            )
        except AIProviderError as err:
            logger.error("AI provider error for INC-%s: %s", incident_id, err)
            return CustomResponse.error(
                message=str(err) or "Failed to generate AI investigation for this incident.",
                errors={"code": "AI_PROVIDER_ERROR", "detail": str(err)},
                code=status.HTTP_502_BAD_GATEWAY,
                error_code="AI_PROVIDER_ERROR",
            )
        except Exception:
            logger.exception("Unexpected error during AI investigation for INC-%s", incident_id)
            return CustomResponse.error(
                message="An unexpected error occurred during AI analysis.",
                errors={"code": "AI_PROVIDER_ERROR"},
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_code="AI_PROVIDER_ERROR",
            )
