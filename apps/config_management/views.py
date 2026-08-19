from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import Serializer
from rest_framework.views import APIView

from .responses import CustomResponseMixin
from .pagination import Pagination
from .filters import CustomOrderingFilter


class BaseViewSetConfig:
    """
    Shared configuration for ViewSets.

    Provides common:

    - Authentication
    - Permissions
    - Pagination
    - Filtering
    - Search
    - Ordering

    Intended to be inherited by base ViewSet classes to avoid
    duplicating common DRF configuration.
    """

    pagination_class = Pagination
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, CustomOrderingFilter]


class CustomBaseAPIView(CustomResponseMixin, APIView):
    """
    Base APIView providing:

    - Standard response structure
    - Standard exception handling
    - Authentication/permission enforcement

    Use for APIs that do not require queryset/serializer support.
    """

    permission_classes = [IsAuthenticated]


class CustomBaseGenericViewSet(BaseViewSetConfig, CustomResponseMixin, viewsets.GenericViewSet):
    """
    Base GenericViewSet providing:

    - Standard response structure
    - Standard exception handling
    - Shared ViewSet configuration via BaseViewSetConfig

    Intended for composing custom ViewSets using DRF mixins.

    Subclasses should define `serializer_class` or override
    `get_serializer_class()`.
    """

    def get_serializer_class(self):
        """
        Return a fallback serializer.

        Subclasses should define `serializer_class` or override this method
        to provide the appropriate serializer.
        """
        return Serializer


class CustomBaseViewSet(BaseViewSetConfig, CustomResponseMixin, viewsets.ModelViewSet):
    """
    Base ModelViewSet providing:

    - Standard response structure
    - Standard exception handling
    - Shared ViewSet configuration via BaseViewSetConfig
    - Customized paginated responses

    Suitable for most CRUD APIs.
    """

    def get_paginated_response(self, data, message=None, meta=None):
        assert self.paginator is not None

        return self.paginator.get_paginated_response(data, message=message, meta=meta)

    def perform_create(self, serializer):
        """
        Hook for create operations.
        Automatically assigns `created_by` and `modified_by` if the model supports it.
        """
        kwargs = {}
        if self.request.user and self.request.user.is_authenticated:
            model = getattr(getattr(serializer, "Meta", None), "model", None)
            if model:
                if hasattr(model, "created_by_id"):
                    kwargs["created_by"] = self.request.user
                if hasattr(model, "modified_by_id"):
                    kwargs["modified_by"] = self.request.user
        serializer.save(**kwargs)

    def perform_update(self, serializer):
        """
        Hook for update operations.
        Automatically assigns `modified_by` if the model supports it.
        """
        kwargs = {}
        if self.request.user and self.request.user.is_authenticated:
            model = getattr(getattr(serializer, "Meta", None), "model", None)
            if model and hasattr(model, "modified_by_id"):
                kwargs["modified_by"] = self.request.user
        serializer.save(**kwargs)

    def perform_destroy(self, instance):
        """
        Hook for delete operations.
        Automatically performs a soft delete if the model supports it.
        """
        if hasattr(instance, "soft_delete"):
            user = self.request.user if self.request.user.is_authenticated else None
            instance.soft_delete(user=user)
        else:
            instance.delete()
