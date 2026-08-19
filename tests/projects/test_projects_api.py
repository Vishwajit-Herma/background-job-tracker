import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.projects.models import Project
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
    team = Team.objects.create(name="Team 1", slug="team-1", owner=user1)
    return team


@pytest.fixture
def team2(user2):
    team = Team.objects.create(name="Team 2", slug="team-2", owner=user2)
    return team


@pytest.fixture
def project1(team1):
    return Project.objects.create(team=team1, name="Project 1")


@pytest.fixture
def project2(team2):
    return Project.objects.create(team=team2, name="Project 2")


@pytest.mark.django_db
class TestProjectAPI:
    def test_tenant_isolation(self, api_client, user1, user2, team1, team2, project1, project2):
        """User 1 should only see Project 1, not Project 2."""
        api_client.force_authenticate(user=user1)
        url = reverse("api:projects:project-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json().get("data", [])
        assert len(data) == 1
        assert data[0]["id"] == project1.id

        # Directly fetching Project 2 should fail with 404 because get_queryset isolates it
        detail_url = reverse("api:projects:project-detail", args=[project2.id])
        response = api_client.get(detail_url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_member_can_create_and_update(self, api_client, user1, team1):
        """Active members can create and update projects."""
        api_client.force_authenticate(user=user1)
        url = reverse("api:projects:project-list")

        # Create
        data = {"team": team1.id, "name": "New Project"}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        project_id = response.json()["data"]["id"]

        # Update
        detail_url = reverse("api:projects:project-detail", args=[project_id])
        update_data = {"name": "Updated Project"}
        response = api_client.patch(detail_url, update_data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["name"] == "Updated Project"

    def test_cannot_create_for_other_team(self, api_client, user1, team2):
        """User cannot create a project for a team they do not belong to."""
        api_client.force_authenticate(user=user1)
        url = reverse("api:projects:project-list")

        data = {"team": team2.id, "name": "Hack Project"}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_member_delete_denial(self, api_client, user2, team1, project1):
        """Regular member cannot delete a project."""
        # Add user2 to team1 as a regular member
        team1.add_user(user2, role="member")

        api_client.force_authenticate(user=user2)
        detail_url = reverse("api:projects:project-detail", args=[project1.id])

        response = api_client.delete(detail_url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_owner_delete(self, api_client, user1, team1, project1):
        """Owner can delete a project, which triggers soft delete."""
        api_client.force_authenticate(user=user1)
        detail_url = reverse("api:projects:project-detail", args=[project1.id])

        response = api_client.delete(detail_url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it was soft deleted, not hard deleted
        project1.refresh_from_db()
        assert project1.is_deleted is True
        assert project1.deleted_at is not None
        assert project1.deleted_by == user1

    def test_soft_deleted_project_excluded_from_list(self, api_client, user1, team1, project1):
        """A soft-deleted project should not appear in the standard API list."""
        project1.soft_delete(user=user1)

        api_client.force_authenticate(user=user1)
        url = reverse("api:projects:project-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json().get("data", [])
        assert len(data) == 0

    def test_created_by_and_modified_by_populated(self, api_client, user1, team1):
        """Ensure BaseViewSet automatically populates created_by and modified_by."""
        api_client.force_authenticate(user=user1)
        url = reverse("api:projects:project-list")

        # Create
        data = {"team": team1.id, "name": "Audit Project"}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        project_id = response.json()["data"]["id"]

        # We must refresh from DB because Serializer response has integer ID for ForeignKeys
        project = Project.objects.get(id=project_id)
        assert project.created_by == user1
        assert project.modified_by == user1

        # Update
        detail_url = reverse("api:projects:project-detail", args=[project_id])
        api_client.patch(detail_url, {"name": "Audit Update"})
        project.refresh_from_db()
        assert project.modified_by == user1

    def test_unauthenticated_access_denied(self, api_client):
        """Unauthenticated users should receive 401 Unauthorized."""
        url = reverse("api:projects:project-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_team_on_create_returns_400(self, api_client, user1):
        """Missing team on creation should return 400 Bad Request, not 403."""
        api_client.force_authenticate(user=user1)
        url = reverse("api:projects:project-list")

        data = {"name": "Test Project"}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_inactive_teammember_cannot_access(self, api_client, user2, team1, project1):
        """Inactive TeamMember cannot read, create or update."""
        # Add user2 to team1 but make them inactive
        member = team1.add_user(user2, role="member")
        member.is_active = False
        member.save()

        api_client.force_authenticate(user=user2)
        url = reverse("api:projects:project-list")

        # 1. Read: Should return empty list because get_queryset filters out inactive members
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json().get("data", [])) == 0

        # 2. Create: Should return 403 because they are not an active member
        data = {"team": team1.id, "name": "Inactive Project"}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # 3. Update: Should return 404 because get_queryset excludes it
        detail_url = reverse("api:projects:project-detail", args=[project1.id])
        response = api_client.patch(detail_url, {"name": "Hacked Update"})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_restore_action(self, api_client, user1, user2, team1, project1):
        """Owners can restore a soft-deleted project."""
        # Setup: user1 is owner, user2 is regular member
        team1.add_user(user2, role="member")

        # Soft delete the project
        project1.soft_delete(user=user1)
        assert project1.is_deleted is True

        restore_url = reverse("api:projects:project-restore", args=[project1.id])

        # 1. Regular member cannot restore
        api_client.force_authenticate(user=user2)
        response = api_client.post(restore_url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # 2. Owner can restore
        api_client.force_authenticate(user=user1)
        response = api_client.post(restore_url)
        assert response.status_code == status.HTTP_200_OK

        # Verify it was restored
        project1.refresh_from_db()
        assert project1.is_deleted is False
        assert project1.deleted_at is None
        assert project1.deleted_by is None

        # It should now appear in the list again
        list_url = reverse("api:projects:project-list")
        response = api_client.get(list_url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json().get("data", [])) == 1

    def test_restore_fails_if_duplicate_name_exists(self, api_client, user1, team1, project1):
        """Cannot restore a project if another active project has taken its name."""
        # 1. Soft delete project1 ("Project 1")
        project1.soft_delete(user=user1)

        api_client.force_authenticate(user=user1)

        # 2. Create a new project with the exact same name "Project 1"
        url = reverse("api:projects:project-list")
        response = api_client.post(url, {"team": team1.id, "name": "Project 1"})
        assert response.status_code == status.HTTP_201_CREATED

        # 3. Attempt to restore the original project1
        restore_url = reverse("api:projects:project-restore", args=[project1.id])
        response = api_client.post(restore_url)
        # It should gracefully fail with 400 Bad Request instead of 500 Server Error
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot restore" in str(response.content)

    def test_invalid_team_id_does_not_crash(self, api_client, user1):
        """Passing a non-integer team ID should not crash the server with a 500 error."""
        api_client.force_authenticate(user=user1)
        url = reverse("api:projects:project-list")

        # Pass a string instead of an integer for team ID
        response = api_client.post(url, {"team": "invalid-string", "name": "Crash Test"})

        # It should either return 403 Forbidden (caught by permission) or 400 Bad Request (caught by serializer)
        # We just want to ensure it doesn't return 500 Internal Server Error
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST]

    def test_cannot_create_project_in_inactive_team(self, api_client, user1, team1):
        """Users cannot create projects if their team has been deactivated."""
        # Deactivate the team
        team1.is_active = False
        team1.save()

        api_client.force_authenticate(user=user1)
        url = reverse("api:projects:project-list")

        # Attempt to create
        data = {"team": team1.id, "name": "Should Fail Project"}
        response = api_client.post(url, data)

        # It should return 403 Forbidden because the permission class blocks it
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_post_list_payload_does_not_crash(self, api_client, user1):
        """Posting a list instead of a dictionary should not crash the server with a 500 error."""
        api_client.force_authenticate(user=user1)
        url = reverse("api:projects:project-list")

        # Pass a list instead of a dict
        response = api_client.post(url, [{"team": 1, "name": "Crash Test"}], format="json")

        # We just want to ensure it doesn't return 500 Internal Server Error
        # It will likely return 400 Bad Request
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
