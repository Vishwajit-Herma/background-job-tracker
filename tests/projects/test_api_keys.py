import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.projects.models import Project, APIKey
from apps.teams.models import Team
from apps.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user1(db):
    return User.objects.create(email="user1@example.com", password="password")


@pytest.fixture
def user2(db):
    return User.objects.create(email="user2@example.com", password="password")


@pytest.fixture
def team1(user1):
    return Team.objects.create(name="Team 1", slug="team-1", owner=user1)


@pytest.fixture
def team2(user2):
    return Team.objects.create(name="Team 2", slug="team-2", owner=user2)


@pytest.fixture
def project1(team1):
    return Project.objects.create(team=team1, name="Project 1")


@pytest.fixture
def project2(team2):
    return Project.objects.create(team=team2, name="Project 2")


@pytest.mark.django_db
class TestAPIKeys:
    def get_list_url(self, project_id):
        return reverse("api:projects:apikey-list", kwargs={"project_pk": project_id})

    def get_detail_url(self, project_id, key_id):
        return reverse(
            "api:projects:apikey-detail", kwargs={"project_pk": project_id, "pk": key_id}
        )

    def get_revoke_url(self, project_id, key_id):
        return reverse(
            "api:projects:apikey-revoke", kwargs={"project_pk": project_id, "pk": key_id}
        )

    def test_owner_can_create_api_key(self, api_client, user1, project1):
        """Owner can create an API key, and raw secret is returned exactly once."""
        api_client.force_authenticate(user=user1)
        url = self.get_list_url(project1.id)

        response = api_client.post(url, {"name": "Production SDK"})
        assert response.status_code == status.HTTP_201_CREATED

        data = response.json().get("data", {})
        assert "key" in data
        assert data["key"].startswith("rk_live_")
        assert data["key_prefix"] == data["key"][:12]
        assert data["name"] == "Production SDK"

        # The key hash should never be exposed
        assert "key_hash" not in data

        # Verify database storage
        key_obj = APIKey.objects.get(id=data["id"])
        assert key_obj.verify_key(data["key"]) is True

    def test_raw_key_is_never_returned_again(self, api_client, user1, project1):
        """After creation, listing and retrieving must not include the raw key."""
        api_client.force_authenticate(user=user1)
        # Create
        create_resp = api_client.post(self.get_list_url(project1.id), {"name": "SDK"})
        key_id = create_resp.json()["data"]["id"]

        # List
        list_resp = api_client.get(self.get_list_url(project1.id))
        assert list_resp.status_code == status.HTTP_200_OK
        list_data = list_resp.json().get("data", [])
        assert len(list_data) == 1
        assert "key" not in list_data[0]
        assert "key_hash" not in list_data[0]

        # Detail
        detail_resp = api_client.get(self.get_detail_url(project1.id, key_id))
        assert detail_resp.status_code == status.HTTP_200_OK
        detail_data = detail_resp.json().get("data", {})
        assert "key" not in detail_data
        assert "key_hash" not in detail_data

    def test_member_receives_403(self, api_client, user1, user2, team1, project1):
        """Regular team members cannot access any API Key endpoints."""
        team1.add_user(user2, role="member")
        api_client.force_authenticate(user=user2)

        # Create fails
        response = api_client.post(self.get_list_url(project1.id), {"name": "Hack"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # List fails
        response = api_client.get(self.get_list_url(project1.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_tenant_isolation(self, api_client, user1, user2, project1, project2):
        """Users in one team cannot access keys in another team's project."""
        # Create a key in Project 2 (Team 2)
        key_obj, _ = APIKey.create_key(project=project2, name="P2 Key", user=user2)

        # User 1 attempts to access Project 2's keys
        api_client.force_authenticate(user=user1)

        # 1. Using P2's actual ID
        response = api_client.get(self.get_list_url(project2.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # 2. Try to list P1's keys but somehow get P2's key (not possible, but let's test detail)
        response = api_client.get(self.get_detail_url(project1.id, key_obj.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_receives_401(self, api_client, project1):
        """Unauthenticated requests receive 401."""
        response = api_client.get(self.get_list_url(project1.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_revoke_key(self, api_client, user1, project1):
        """Revoking an active key sets revoked_at and revoked_by and prevents verification."""
        api_client.force_authenticate(user=user1)
        # Create
        create_resp = api_client.post(self.get_list_url(project1.id), {"name": "To Revoke"})
        data = create_resp.json().get("data", {})
        key_id = data["id"]
        raw_key = data["key"]

        # Key is active
        key_obj = APIKey.objects.get(id=key_id)
        assert key_obj.is_revoked is False
        assert key_obj.verify_key(raw_key) is True

        # Revoke
        revoke_url = self.get_revoke_url(project1.id, key_id)
        revoke_resp = api_client.post(revoke_url)
        assert revoke_resp.status_code == status.HTTP_200_OK

        # Key is revoked
        key_obj.refresh_from_db()
        assert key_obj.is_revoked is True
        assert key_obj.revoked_at is not None
        assert key_obj.revoked_by == user1

        # Validation fails
        assert key_obj.verify_key(raw_key) is False

    def test_revoking_already_revoked_key_fails(self, api_client, user1, project1):
        """Cannot revoke a key that is already revoked."""
        api_client.force_authenticate(user=user1)
        # Create & Revoke
        create_resp = api_client.post(self.get_list_url(project1.id), {"name": "Double Revoke"})
        key_id = create_resp.json()["data"]["id"]

        revoke_url = self.get_revoke_url(project1.id, key_id)
        api_client.post(revoke_url)

        # Revoke again
        revoke_resp = api_client.post(revoke_url)
        assert revoke_resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already revoked" in str(revoke_resp.content)

    def test_create_key_validation(self, api_client, user1, project1):
        """Name field validation checks."""
        api_client.force_authenticate(user=user1)
        url = self.get_list_url(project1.id)

        # Missing name
        resp = api_client.post(url, {})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

        # Blank name
        resp = api_client.post(url, {"name": ""})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

        # Too long
        resp = api_client.post(url, {"name": "a" * 256})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_create_key_for_deleted_project(self, api_client, user1, project1):
        """If project is deleted, we cannot create a key."""
        project1.soft_delete(user=user1)

        api_client.force_authenticate(user=user1)
        response = api_client.post(self.get_list_url(project1.id), {"name": "Zombie Key"})

        # Because the Project is soft-deleted, it won't be found by the permission class
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_create_key_for_inactive_project(self, api_client, user1, project1):
        """If project is inactive, we cannot create a key."""
        project1.status = "inactive"
        project1.save()

        api_client.force_authenticate(user=user1)
        response = api_client.post(self.get_list_url(project1.id), {"name": "Inactive Key"})

        # This is caught by the serializer validation
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "inactive" in str(response.content)

    def test_cannot_create_duplicate_api_key_name(self, api_client, user1, project1):
        """Keys must have unique names within the same active project."""
        api_client.force_authenticate(user=user1)

        # Create first key
        response1 = api_client.post(self.get_list_url(project1.id), {"name": "Unique Name"})
        assert response1.status_code == status.HTTP_201_CREATED

        # Create second key with same name
        response2 = api_client.post(self.get_list_url(project1.id), {"name": "Unique Name"})
        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        assert "An active API key with this name already exists in this project" in str(
            response2.content
        )
