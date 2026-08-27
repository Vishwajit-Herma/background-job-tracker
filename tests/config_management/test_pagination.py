import pytest
from rest_framework.test import APIClient
from django.urls import path
from apps.config_management.views import CustomBaseViewSet
from apps.users.models import User
from rest_framework import serializers


# Dummy serializer and viewset
class DummyData:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class DummySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class DummyViewSet(CustomBaseViewSet):
    serializer_class = DummySerializer

    def get_queryset(self):
        return [DummyData(i, f"Name {i}") for i in range(1, 101)]


urlpatterns = [
    path("test/paginated/", DummyViewSet.as_view({"get": "list"})),
]


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create(email="test@example.com", password="password")


@pytest.mark.urls(__name__)
@pytest.mark.django_db
def test_pagination_default(client, user):
    client.force_authenticate(user=user)
    response = client.get("/test/paginated/")
    assert response.status_code == 200
    assert response.data["status"] == "success"
    assert "page" in response.data
    assert "limit" in response.data
    assert response.data["limit"] == 15  # from settings
    assert response.data["totalItems"] == 100
    assert response.data["totalPages"] == 7
    assert len(response.data["data"]) == 15


@pytest.mark.urls(__name__)
@pytest.mark.django_db
def test_pagination_limit(client, user):
    client.force_authenticate(user=user)
    response = client.get("/test/paginated/?limit=10")
    assert response.status_code == 200
    assert response.data["limit"] == 10
    assert response.data["totalItems"] == 100
    assert response.data["totalPages"] == 10
    assert len(response.data["data"]) == 10


@pytest.mark.urls(__name__)
@pytest.mark.django_db
def test_no_pagination(client, user):
    client.force_authenticate(user=user)
    response = client.get("/test/paginated/?no_pagination=true")
    assert response.status_code == 200
    assert "page" not in response.data
    assert "limit" not in response.data
    assert len(response.data["data"]) == 100
