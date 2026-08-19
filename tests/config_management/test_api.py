import pytest
from rest_framework.test import APIClient
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from django.urls import path
from apps.config_management.views import CustomBaseAPIView
from apps.users.models import User
from rest_framework import status


# Dummy views for testing API responses and exception handling
class SuccessView(CustomBaseAPIView):
    def get(self, request):
        return Response({"name": "test"}, status=status.HTTP_200_OK)


class ErrorView(CustomBaseAPIView):
    def get(self, request):
        raise ValidationError({"name": ["This field is required."]})


class NotFoundView(CustomBaseAPIView):
    def get(self, request):
        raise NotFound("Not found here.")


class PermDeniedView(CustomBaseAPIView):
    def get(self, request):
        raise PermissionDenied("Denied.")


urlpatterns = [
    path("test/success/", SuccessView.as_view()),
    path("test/error/", ErrorView.as_view()),
    path("test/notfound/", NotFoundView.as_view()),
    path("test/permdenied/", PermDeniedView.as_view()),
]


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create(email="test@example.com", password="password")


@pytest.mark.urls(__name__)
@pytest.mark.django_db
def test_success_response(client, user):
    client.force_authenticate(user=user)
    response = client.get("/test/success/")
    assert response.status_code == 200
    assert response.data["status"] == "success"
    assert response.data["status_code"] == 200
    assert response.data["data"] == {"name": "test"}


@pytest.mark.urls(__name__)
@pytest.mark.django_db
def test_validation_error_response(client, user):
    client.force_authenticate(user=user)
    response = client.get("/test/error/")
    assert response.status_code == 400
    assert response.data["status"] == "error"
    assert response.data["status_code"] == 400
    assert "errors" in response.data
    assert response.data["errors"]["name"] == ["This field is required."]


@pytest.mark.urls(__name__)
@pytest.mark.django_db
def test_notfound_response(client, user):
    client.force_authenticate(user=user)
    response = client.get("/test/notfound/")
    assert response.status_code == 404
    assert response.data["status"] == "error"
    assert response.data["status_code"] == 404
    assert response.data["message"] == "Not found here."


@pytest.mark.urls(__name__)
@pytest.mark.django_db
def test_permission_denied_response(client, user):
    client.force_authenticate(user=user)
    response = client.get("/test/permdenied/")
    assert response.status_code == 403
    assert response.data["status"] == "error"
    assert response.data["status_code"] == 403
    assert response.data["message"] == "Denied."
