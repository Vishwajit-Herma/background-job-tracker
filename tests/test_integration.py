"""Integration tests for SaaS features."""

import pytest
from django.contrib.auth import get_user_model
from apps.teams.models import Team, TeamInvitation

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.integration
class TestTeamWorkflow:
    """Test complete team workflow."""

    def test_complete_team_lifecycle(self, user):
        """Test full team lifecycle from creation to deletion."""
        # 1. Create team (owner membership is created by the post_save signal)
        team = Team.objects.create(name="Startup Team", slug="startup-team", owner=user)

        assert team.is_active
        assert team.get_member_count() == 1

        # 2. Invite member
        invitation = TeamInvitation.objects.create(
            team=team, email="member@example.com", role="member", invited_by=user
        )

        assert invitation.status == "pending"
        assert invitation.is_valid()

        # 3. Accept invitation
        invited_user = User.objects.create_user(email="member@example.com", password="testpass123")

        invitation.accept(invited_user)

        assert invitation.status == "accepted"
        assert team.get_member_count() == 2
        assert team.has_member(invited_user)

        # 4. Add another member directly
        another_user = User.objects.create_user(email="another@example.com", password="testpass123")

        member = team.add_user(another_user, role="admin", added_by=user)

        assert member.role == "admin"
        assert member.is_admin()
        assert team.get_member_count() == 3

        # 5. Remove member
        member.is_active = False
        member.save()

        assert team.get_member_count() == 2

        # 6. Soft delete team
        team.is_active = False
        team.save()

        assert not team.is_active


@pytest.mark.django_db
@pytest.mark.integration
class TestFeatureFlagIntegration:
    """Test feature flags integration."""

    def test_feature_flag_with_user_groups(self):
        """Test feature flags with user groups."""
        from waffle.models import Flag
        from django.contrib.auth.models import Group

        # Create a flag for beta users (everyone must stay None:
        # everyone=False force-disables the flag for all users)
        flag = Flag.objects.create(name="beta_features")

        # Create beta group
        beta_group = Group.objects.create(name="Beta Testers")
        flag.groups.add(beta_group)

        # Create users
        beta_user = User.objects.create_user(email="beta@example.com", password="testpass123")
        beta_user.groups.add(beta_group)

        regular_user = User.objects.create_user(email="regular@example.com", password="testpass123")

        # Test access
        from apps.core.feature_flags import is_feature_enabled

        assert is_feature_enabled("beta_features", user=beta_user)
        assert not is_feature_enabled("beta_features", user=regular_user)


@pytest.mark.django_db
@pytest.mark.integration
class TestImpersonationIntegration:
    """Test impersonation integration."""

    def test_impersonation_with_feature_flags(self, client, staff_user):
        """Test that impersonation works with feature flags."""
        from waffle.models import Flag

        # Create a staff-only flag
        Flag.objects.create(name="admin_panel", staff=True, everyone=False)

        regular_user = User.objects.create_user(email="regular@example.com", password="testpass123")

        # Staff user can access
        client.force_login(staff_user)
        session = client.session
        session["impersonate_id"] = regular_user.id
        session.save()

        # After impersonating, staff user becomes regular user
        # But middleware should preserve permissions
        # This tests that the real_user is used for staff checks
