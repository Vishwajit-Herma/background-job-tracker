import math

from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class Pagination(PageNumberPagination):
    """
    Custom DRF paginator supporting configurable page sizes,
    optional pagination bypass, and a standardized paginated response.
    """

    page_size_query_param = "limit"
    no_pagination_query_param = "no_pagination"

    def paginate_queryset(self, queryset, request, view=None):
        """
        Skip pagination when the no_pagination query parameter is truthy.
        """
        val = request.query_params.get(self.no_pagination_query_param, "").lower()
        if val in ("true", "1", "yes", "on"):
            return None
        return super().paginate_queryset(queryset, request, view)

    @staticmethod
    def _validate_positive_integer(value: str, field_name: str) -> int:
        """
        Validate that a value is a positive integer.
        """
        try:
            value = int(value)
        except (TypeError, ValueError) as err:
            raise ValidationError({field_name: "Must be a valid integer."}) from err

        if value < 1:
            raise ValidationError(
                {
                    field_name: (
                        "Limit values must be positive integers."
                        if field_name == "limit"
                        else "Page values must be positive integers."
                    )
                }
            )

        return value

    def get_page_size(self, request):
        """
        Override to validate that page size is positive.
        """
        # Check the raw query parameter before parent class sanitizes it
        if self.page_size_query_param in request.query_params:
            self._validate_positive_integer(
                request.query_params.get(self.page_size_query_param), self.page_size_query_param
            )

        # Let parent class handle the rest (max_page_size, defaults, etc.)
        return super().get_page_size(request)

    def get_paginated_response(self, data, message: str | None = None, meta: dict | None = None):
        """
        Return a standardized paginated response.
        """
        page = getattr(self, "page", None)
        req = getattr(self, "request", None)

        if page is None or req is None:
            try:
                page_size = self.get_page_size(req) if req is not None else (self.page_size or 0)
            except Exception:
                page_size = self.page_size or 0

            total_items = len(data) if isinstance(data, (list, tuple)) else 0
            total_pages = math.ceil(total_items / page_size) if page_size else 0

            response_data = {
                "data": data,
                "page": 1,
                "limit": page_size,
                "totalPages": total_pages,
                "totalItems": total_items,
            }
        else:
            page_size = self.get_page_size(req)

            response_data = {
                "data": data,
                "page": page.number,
                "limit": page_size,
                "totalPages": page.paginator.num_pages,
                "totalItems": page.paginator.count,
            }

        if message:
            response_data["message"] = message

        if meta:
            response_data["meta"] = meta

        return Response(response_data)

    def get_page_number(self, request, paginator):
        """
        Return the requested page number after validating it.
        """
        page_number = super().get_page_number(request, paginator)
        self._validate_positive_integer(page_number, "page")
        return page_number
