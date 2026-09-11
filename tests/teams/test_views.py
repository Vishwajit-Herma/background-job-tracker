"""Tests for teams views."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.teams.models import Team, TeamCreationSetting, TeamInvitation, TeamMember

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(email="user@example.com", password="testpass123")


@pytest.fixture
def team_owner(db):
    """Create a team owner."""
    return User.objects.create_user(email="owner@example.com", password="testpass123")


@pytest.fixture
def team(db, team_owner):
    """Create a test team (owner membership is created by the post_save signal)."""
    return Team.objects.create(
        name="Test Team", slug="test-team", owner=team_owner, description="A test team"
    )


@pytest.mark.django_db
class TestTeamListView:
    """Test TeamListView."""

    def test_list_teams_authenticated(self, client, user, team):
        """Test authenticated user can view their teams."""
        # Add user to team
        TeamMember.objects.create(team=team, user=user, role="member")

        client.force_login(user)
        response = client.get(reverse("teams:list"))

        assert response.status_code == 200
        assert team in response.context["teams"]

    def test_list_teams_unauthenticated(self, client):
        """Test unauthenticated user is redirected."""
        response = client.get(reverse("teams:list"))

        assert response.status_code == 302  # Redirect to login


@pytest.mark.django_db
class TestTeamCreateView:
    """Test TeamCreateView."""

    def test_create_team(self, client, user):
        """Test creating a team."""
        client.force_login(user)

        data = {"name": "New Team", "slug": "new-team", "description": "A new team"}

        response = client.post(reverse("teams:create"), data)

        assert response.status_code == 302  # Redirect after success
        assert Team.objects.filter(slug="new-team").exists()

        team = Team.objects.get(slug="new-team")
        assert team.owner == user

    def test_create_team_auto_slug(self, client, user):
        """Test creating team with auto-generated slug."""
        client.force_login(user)

        data = {"name": "Another Team", "description": "Auto slug team"}

        response = client.post(reverse("teams:create"), data)

        assert response.status_code == 302
        assert Team.objects.filter(slug="another-team").exists()


@pytest.mark.django_db
class TestTeamDetailView:
    """Test TeamDetailView."""

    def test_view_team_as_member(self, client, user, team):
        """Test viewing team as member."""
        TeamMember.objects.create(team=team, user=user, role="member")

        client.force_login(user)
        response = client.get(reverse("teams:detail", kwargs={"team_slug": team.slug}))

        assert response.status_code == 200
        assert response.context["team"] == team

    def test_view_team_non_member(self, client, user, team):
        """Test non-member cannot view team."""
        client.force_login(user)
        response = client.get(reverse("teams:detail", kwargs={"team_slug": team.slug}))

        assert response.status_code == 403  # Forbidden


@pytest.mark.django_db
class TestTeamUpdateView:
    """Test TeamUpdateView."""

    def test_update_team_as_admin(self, client, user, team):
        """Test updating team as admin."""
        TeamMember.objects.create(team=team, user=user, role="admin")

        client.force_login(user)

        data = {"name": "Updated Team Name", "description": "Updated description"}

        response = client.post(reverse("teams:update", kwargs={"team_slug": team.slug}), data)

        assert response.status_code == 302

        team.refresh_from_db()
        assert team.name == "Updated Team Name"

    def test_update_team_as_member_forbidden(self, client, user, team):
        """Test regular member cannot update team."""
        TeamMember.objects.create(team=team, user=user, role="member")

        client.force_login(user)

        data = {"name": "Hacked Name", "description": "Should not work"}

        response = client.post(reverse("teams:update", kwargs={"team_slug": team.slug}), data)

        assert response.status_code == 403


@pytest.mark.django_db
class TestTeamInvitationViews:
    """Test team invitation views."""

    def test_create_invitation_as_admin(self, client, user, team):
        """Test creating invitation as admin."""
        TeamMember.objects.create(team=team, user=user, role="admin")

        client.force_login(user)

        data = {"email": "newmember@example.com", "role": "member"}

        response = client.post(reverse("teams:invite", kwargs={"team_slug": team.slug}), data)

        assert response.status_code == 302

        assert TeamInvitation.objects.filter(team=team, email="newmember@example.com").exists()

    def test_accept_invitation(self, client, user, team, team_owner):
        """Test accepting invitation."""
        invitation = TeamInvitation.objects.create(
            team=team, email=user.email, role="member", invited_by=team_owner
        )

        client.force_login(user)

        response = client.get(
            reverse("teams:invitation_accept", kwargs={"token": invitation.token})
        )

        assert response.status_code == 302

        # Check member was created
        assert TeamMember.objects.filter(team=team, user=user).exists()

    def test_accept_invitation_wrong_email(self, client, user, team, team_owner):
        """Test accepting invitation with wrong email."""
        invitation = TeamInvitation.objects.create(
            team=team, email="different@example.com", role="member", invited_by=team_owner
        )

        client.force_login(user)

        response = client.get(
            reverse("teams:invitation_accept", kwargs={"token": invitation.token})
        )

        assert response.status_code == 302

        # Member should not be created
        assert not TeamMember.objects.filter(team=team, user=user).exists()

    def test_decline_invitation(self, client, user, team, team_owner):
        """Test declining invitation."""
        invitation = TeamInvitation.objects.create(
            team=team, email=user.email, role="member", invited_by=team_owner
        )

        client.force_login(user)

        response = client.post(
            reverse("teams:invitation_decline", kwargs={"token": invitation.token})
        )

        assert response.status_code == 302

        invitation.refresh_from_db()
        assert invitation.status == "declined"


@pytest.mark.django_db
class TestTeamMemberViews:
    """Test team member views."""

    def test_remove_member_as_admin(self, client, user, team, team_owner):
        """Test removing member as admin."""
        # Create member to remove
        member_to_remove = User.objects.create_user(
            email="remove@example.com", password="testpass123"
        )

        member = TeamMember.objects.create(team=team, user=member_to_remove, role="member")

        # Add user as admin
        TeamMember.objects.create(team=team, user=user, role="admin")

        client.force_login(user)

        response = client.post(
            reverse("teams:member_remove", kwargs={"team_slug": team.slug, "member_id": member.id})
        )

        assert response.status_code == 302

        member.refresh_from_db()
        assert member.is_active is False

    def test_cannot_remove_owner(self, client, user, team, team_owner):
        """Test cannot remove team owner."""
        owner_member = TeamMember.objects.get(team=team, user=team_owner, role="owner")

        # Add user as admin
        TeamMember.objects.create(team=team, user=user, role="admin")

        client.force_login(user)

        response = client.post(
            reverse(
                "teams:member_remove", kwargs={"team_slug": team.slug, "member_id": owner_member.id}
            )
        )

        assert response.status_code == 302

        owner_member.refresh_from_db()
        assert owner_member.is_active is True  # Still active

    def test_leave_team(self, client, user, team):
        """Test leaving a team."""
        member = TeamMember.objects.create(team=team, user=user, role="member")

        client.force_login(user)

        response = client.post(reverse("teams:leave", kwargs={"team_slug": team.slug}))

        assert response.status_code == 302

        member.refresh_from_db()
        assert member.is_active is False

    def test_owner_cannot_leave(self, client, team_owner, team):
        """Test owner cannot leave their team."""
        client.force_login(team_owner)

        response = client.post(reverse("teams:leave", kwargs={"team_slug": team.slug}))

        assert response.status_code == 302

        # Owner membership should still be active
        owner_member = TeamMember.objects.get(team=team, user=team_owner)
        assert owner_member.is_active is True


@pytest.mark.django_db
class TestTeamAPILimitAndCreation:
    """Tests for team creation limits and non-staff self-serve creation."""

    def test_non_staff_user_can_create_team_api(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.post(
            "/api/teams/", {"name": "User Alpha Team", "slug": "user-alpha-team"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Team.objects.filter(slug="user-alpha-team", owner=user).exists()

    def test_duplicate_team_name_returns_clean_validation_error(self, user):
        client = APIClient()
        client.force_authenticate(user=user)

        # 1. Create first team with name "My Team"
        res1 = client.post("/api/teams/", {"name": "My Team"})
        assert res1.status_code == status.HTTP_201_CREATED

        # 2. Try to create duplicate team with same name
        other_user = User.objects.create_user(
            email="other_creator@example.com", password="password123"
        )
        client.force_authenticate(user=other_user)
        res2 = client.post("/api/teams/", {"name": "My Team"})
        assert res2.status_code == status.HTTP_400_BAD_REQUEST
        err_data = res2.data.get("errors", res2.data)
        assert "A team with this name already exists" in str(err_data)

    def test_team_limit_enforced_api(self, user, monkeypatch):
        monkeypatch.setattr(
            "apps.teams.models.TeamCreationSetting.get_max_teams_limit",
            classmethod(lambda cls: 2),
        )
        client = APIClient()
        client.force_authenticate(user=user)

        # Create first 2 teams -> succeeds
        res1 = client.post("/api/teams/", {"name": "Team 1", "slug": "team-1"})
        assert res1.status_code == status.HTTP_201_CREATED

        res2 = client.post("/api/teams/", {"name": "Team 2", "slug": "team-2"})
        assert res2.status_code == status.HTTP_201_CREATED

        # 3rd team -> blocked with 400 validation error
        res3 = client.post("/api/teams/", {"name": "Team 3", "slug": "team-3"})
        assert res3.status_code == status.HTTP_400_BAD_REQUEST
        err_data = res3.data.get("errors", res3.data)
        assert "maximum limit of 2 active teams" in str(err_data)

    def test_team_limit_unlimited_when_none(self, user, monkeypatch):
        monkeypatch.setattr(
            "apps.teams.models.TeamCreationSetting.get_max_teams_limit",
            classmethod(lambda cls: None),
        )
        client = APIClient()
        client.force_authenticate(user=user)

        for i in range(4):
            res = client.post("/api/teams/", {"name": f"Team {i}", "slug": f"team-{i}"})
            assert res.status_code == status.HTTP_201_CREATED

    def test_db_setting_overrides_settings_file(self, user, settings):
        settings.MAX_TEAMS_PER_USER = 10
        TeamCreationSetting.objects.create(max_teams_per_user=1)
        assert TeamCreationSetting.get_max_teams_limit() == 1

        client = APIClient()
        client.force_authenticate(user=user)
        res1 = client.post("/api/teams/", {"name": "Team 1", "slug": "team-1"})
        assert res1.status_code == status.HTTP_201_CREATED

        res2 = client.post("/api/teams/", {"name": "Team 2", "slug": "team-2"})
        assert res2.status_code == status.HTTP_400_BAD_REQUEST

    def test_db_setting_blank_means_unlimited(self, user, settings):
        settings.MAX_TEAMS_PER_USER = 1
        # In DB, max_teams_per_user is None (blank)
        TeamCreationSetting.objects.create(max_teams_per_user=None)
        assert TeamCreationSetting.get_max_teams_limit() is None

        client = APIClient()
        client.force_authenticate(user=user)
        for i in range(3):
            res = client.post(
                "/api/teams/", {"name": f"Unlimited Team {i}", "slug": f"unl-team-{i}"}
            )
            assert res.status_code == status.HTTP_201_CREATED

    def test_staff_and_superuser_bypass_limit(self, user, monkeypatch):
        monkeypatch.setattr(
            "apps.teams.models.TeamCreationSetting.get_max_teams_limit",
            classmethod(lambda cls: 1),
        )
        user.is_staff = True
        user.save()

        client = APIClient()
        client.force_authenticate(user=user)
        res1 = client.post("/api/teams/", {"name": "Staff Team 1", "slug": "staff-team-1"})
        assert res1.status_code == status.HTTP_201_CREATED
        res2 = client.post("/api/teams/", {"name": "Staff Team 2", "slug": "staff-team-2"})
        assert res2.status_code == status.HTTP_201_CREATED

    def test_delete_team_actually_deletes_team_from_database_and_allows_recreating_same_name(
        self, user
    ):
        client = APIClient()
        client.force_authenticate(user=user)

        # 1. Create team
        res1 = client.post("/api/teams/", {"name": "Disposable Team", "slug": "disposable-team"})
        assert res1.status_code == status.HTTP_201_CREATED
        team_id = res1.data.get("data", res1.data)["id"]

        # 2. Delete team
        del_res = client.delete(f"/api/teams/{team_id}/")
        assert del_res.status_code == status.HTTP_204_NO_CONTENT

        # 3. Assert completely deleted from DB (not just inactivated)
        assert not Team.objects.filter(id=team_id).exists()

        # 4. Can recreate team with exact same name/slug without collision
        res2 = client.post("/api/teams/", {"name": "Disposable Team", "slug": "disposable-team"})
        assert res2.status_code == status.HTTP_201_CREATED
        assert Team.objects.filter(slug="disposable-team", owner=user).exists()
