import logging
from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.exceptions import ErrorDetail

logger = logging.getLogger(__name__)

DEFAULT_ERROR_MESSAGE = "Something went wrong."


class CustomResponse(Response):
    """
    Standardized API response wrapper used throughout the application.
    Response formats:
        Success:
        {
            "status_code": 200,
            "status": "success",
            "message": "Retrieved successfully",
            "data": {
                ...
            }
        }

        Paginated Success:
        {
            "status_code": 200,
            "status": "success",
            "message": "Retrieved successfully",
            "data": [
                ...
            ],
            "page": 1,
            "limit": 10,
            "totalPages": 5,
            "totalItems": 50
        }

        Success with Meta:
        {
            "status_code": 200,
            "status": "success",
            "message": "Retrieved successfully",
            "data": {
                ...
            },
            "meta": {
                ...
            }
        }

        Error:
        {
            "status_code": 400,
            "status": "error",
            "message": "Validation failed",
            "errors": {
                ...
            }
        }

        Error with Validation Details:
        {
            "status_code": 400,
            "status": "error",
            "message": "Validation failed",
            "errors": {
                "email": [
                    "This field is required."
                ]
            }
        }
    """

    PAGINATION_KEYS = {"page", "limit", "totalPages", "totalItems"}

    def __init__(
        self,
        *,
        data: Any = None,
        code: int = status.HTTP_200_OK,
        status_text: str = "success",
        message: str = "Success",
        errors: Any = None,
        meta: dict | None = None,
        **kwargs,
    ):
        payload = {
            "status_code": code,
            "status": status_text,
            "message": message,
            "data": [],
        }

        pagination = {}

        if isinstance(data, dict):
            pagination = (
                {key: data[key] for key in self.PAGINATION_KEYS if key in data}
                if isinstance(data, dict)
                else {}
            )

        if data is not None:
            payload["data"] = data.get("data", data) if isinstance(data, dict) else data

        if errors is not None:
            payload["errors"] = errors

        if meta is not None:
            payload["meta"] = meta

        payload.update(pagination)
        extra_keys = [
            k for k in kwargs if k not in ("headers", "content_type", "template_name", "exception")
        ]
        for k in extra_keys:
            payload[k] = kwargs.pop(k)

        super().__init__(payload, status=code, **kwargs)

    @classmethod
    def success(
        cls,
        data: Any = None,
        message: str = "Success",
        meta: dict | None = None,
        code: int = status.HTTP_200_OK,
        **kwargs,
    ):
        return cls(
            data=data, code=code, status_text="success", message=message, meta=meta, **kwargs
        )

    @classmethod
    def error(
        cls, message: str, *, errors: Any = None, code: int = status.HTTP_400_BAD_REQUEST, **kwargs
    ):
        return cls(
            data=None,
            code=code,
            status_text="error",
            message=message,
            errors=errors,
            **kwargs,
        )


def extract_first_error_message(error_data):
    """
    Extract the most meaningful error message from DRF error responses.
    """

    if isinstance(error_data, ErrorDetail):
        return str(error_data)

    if isinstance(error_data, dict):
        for value in error_data.values():
            message = extract_first_error_message(value)
            if message:
                return message

    if isinstance(error_data, (list, tuple)):
        for item in error_data:
            message = extract_first_error_message(item)
            if message:
                return message

    if error_data:
        return str(error_data)

    return DEFAULT_ERROR_MESSAGE


def custom_exception_handler(exc, context):
    """
    Global DRF exception handler.
    Ensures all exceptions follow the CustomResponse structure.
    """

    response = drf_exception_handler(exc, context)
    request = context.get("request")
    view = context.get("view")

    user_id = getattr(getattr(request, "user", None), "id", None)
    view_name = view.__class__.__name__ if view is not None else "UnknownView"

    if response is not None:
        message = extract_first_error_message(response.data)

        if response.status_code == status.HTTP_400_BAD_REQUEST:
            log_func = logger.info if view_name in ("IngestionViewSet", "JobViewSet") else logger.warning
            log_func(
                "ValidationError in %s. user_id=%s errors=%s",
                view_name,
                user_id,
                response.data,
            )
            return CustomResponse.error(
                message=message, errors=response.data, code=response.status_code
            )

        elif response.status_code == status.HTTP_404_NOT_FOUND:
            logger.warning("NotFound in %s. user_id=%s error=%s", view_name, user_id, message)
            return CustomResponse.error(
                message=message,
                code=response.status_code,
            )

        elif response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
            log_func = logger.info if view_name in ("IngestionViewSet", "JobViewSet") else logger.warning
            log_func(
                "Permission/Auth error in %s. user_id=%s error=%s", view_name, user_id, message
            )
            return CustomResponse.error(message=message, code=response.status_code)

        logger.warning(
            "API exception in %s. user_id=%s status=%s error=%s",
            view_name,
            user_id,
            response.status_code,
            response.data,
        )
        return CustomResponse.error(
            message=message, errors=response.data, code=response.status_code
        )

    logger.exception("Unexpected exception in %s. user_id=%s", view_name, user_id)
    return CustomResponse.error(
        message=DEFAULT_ERROR_MESSAGE, code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


class CustomResponseMixin:
    """
    Mixin that wraps all DRF responses in the standardized CustomResponse format and
    delegates exception handling to the global exception handler.
    """

    def _build_response(self, response_data, response_status, status_text, message, meta=None):
        kwargs = {"code": response_status, "status_text": status_text, "message": message}
        if meta:
            kwargs["meta"] = meta

        if status_text == "success":
            kwargs["data"] = response_data
        else:
            kwargs["errors"] = response_data

        return CustomResponse(**kwargs)

    def _extract_message(self, response_data: object) -> str | None:
        if isinstance(response_data, dict):
            return response_data.get("message")
        return None

    def _format_success_response(self, response_data, response_status, custom_message, meta=None):
        return self._build_response(
            response_data, response_status, "success", custom_message or "Success", meta
        )

    def _format_error_response(self, response_data, response_status, custom_message, meta=None):
        return self._build_response(
            response_data, response_status, "error", custom_message or "Error", meta
        )

    def finalize_response(self, request, response, *args, **kwargs):
        if isinstance(response, Response) and not isinstance(response, CustomResponse):
            renderer_context = getattr(response, "renderer_context", None)

            custom_message = self._extract_message(getattr(response, "data", None))

            if response.status_code != status.HTTP_204_NO_CONTENT:
                if response.status_code < 400:
                    meta = getattr(response, "meta", None)
                    if meta is None:
                        meta = (
                            response.data.get("meta") if isinstance(response.data, dict) else None
                        )
                    response = self._format_success_response(
                        response.data, response.status_code, custom_message, meta=meta
                    )
                else:
                    meta = getattr(response, "meta", None)
                    if meta is None:
                        meta = (
                            response.data.get("meta") if isinstance(response.data, dict) else None
                        )
                    response = self._format_error_response(
                        response.data, response.status_code, custom_message, meta=meta
                    )

            if renderer_context:
                response.accepted_renderer = renderer_context.get("accepted_renderer")
                response.accepted_media_type = renderer_context.get("accepted_media_type")
                response.renderer_context = renderer_context

        return super().finalize_response(
            request,
            response,
            *args,
            **kwargs,
        )

    def handle_exception(self, exc):
        return custom_exception_handler(
            exc,
            {
                "view": self,
                "request": self.request,
            },
        )
