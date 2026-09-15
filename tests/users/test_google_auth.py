"""Security and architectural test suite for Google OAuth2 integration."""

import pytest
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.oauth2.client import OAuth2Error
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.urls import reverse

from apps.projects.models import Project
from apps.teams.models import TeamMember

User = get_user_model()


@pytest.fixture
def google_provider(rf):
    """Provides an initialized GoogleProvider instance."""
    request = rf.get("/")
    adapter = get_adapter(request)
    return adapter.get_provider(request, "google")


@pytest.mark.django_db
def test_security_case_a_new_google_user(rf, google_provider):
    """Scenario A: New Google user registration creates an active, non-staff user with verified email."""
    request = rf.get("/")
    adapter = get_adapter(request)

    data = {
        "id": "google-new-uid-001",
        "email": "brandnewuser@gmail.com",
        "email_verified": True,
        "given_name": "Brand",
        "family_name": "New",
    }
    sociallogin = google_provider.sociallogin_from_response(request, data)

    # Pre social login for new user
    adapter.pre_social_login(request, sociallogin)
    assert not sociallogin.is_existing

    # Save user
    user = adapter.save_user(request, sociallogin)

    assert user.pk is not None
    assert user.email == "brandnewuser@gmail.com"
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False
    assert not user.has_usable_password()

    # Verify EmailAddress is marked verified
    email_obj = EmailAddress.objects.get(user=user, email="brandnewuser@gmail.com")
    assert email_obj.verified is True
    assert email_obj.primary is True

    # Verify SocialAccount exists
    social_acc = SocialAccount.objects.get(user=user, uid="google-new-uid-001")
    assert social_acc.provider == "google"


@pytest.mark.django_db
def test_security_case_b_existing_password_user_verified_google_email(rf, google_provider):
    """Scenario B: Existing password user links SocialAccount when Google email is verified.

    Preserves password, allows both password login and social login, and marks EmailAddress verified.
    """
    request = rf.get("/")
    adapter = get_adapter(request)

    # 1. Existing local user with password and unverified EmailAddress
    local_user = User.objects.create_user(
        email="developer@example.com", password="SecurePassword123!"
    )
    EmailAddress.objects.create(
        user=local_user, email=local_user.email, verified=False, primary=True
    )

    initial_user_count = User.objects.count()

    # 2. Google OAuth returns verified matching email (case-insensitive test)
    data = {
        "id": "google-dev-uid-002",
        "email": "DEVELOPER@EXAMPLE.COM",
        "email_verified": True,
    }
    sociallogin = google_provider.sociallogin_from_response(request, data)

    adapter.pre_social_login(request, sociallogin)

    # 3. Assertions: No duplicate user created
    assert User.objects.count() == initial_user_count
    assert sociallogin.user.pk == local_user.pk
    assert sociallogin.is_existing is True

    # 4. Assert SocialAccount linked to existing local user
    assert SocialAccount.objects.filter(user=local_user, uid="google-dev-uid-002").exists()

    # 5. Assert existing password is completely intact and usable
    assert local_user.has_usable_password() is True
    auth_user = authenticate(email="developer@example.com", password="SecurePassword123!")
    assert auth_user is not None
    assert auth_user.pk == local_user.pk

    # 6. Assert EmailAddress record was marked verified
    email_obj = EmailAddress.objects.get(user=local_user, email__iexact="developer@example.com")
    assert email_obj.verified is True


@pytest.mark.django_db
def test_security_case_c_existing_password_user_different_google_email(rf, google_provider):
    """Scenario C: Existing user remains untouched when a social login occurs with a different email."""
    request = rf.get("/")
    adapter = get_adapter(request)

    existing_user = User.objects.create_user(
        email="alice@example.com", password="AlicePassword123!"
    )
    EmailAddress.objects.create(
        user=existing_user, email=existing_user.email, verified=True, primary=True
    )

    data = {
        "id": "google-bob-uid-003",
        "email": "bob@example.com",
        "email_verified": True,
    }
    sociallogin = google_provider.sociallogin_from_response(request, data)

    adapter.pre_social_login(request, sociallogin)
    assert not sociallogin.is_existing

    # Save new social user
    new_user = adapter.save_user(request, sociallogin)

    assert new_user.pk != existing_user.pk
    assert new_user.email == "bob@example.com"
    assert User.objects.count() == 2

    # Verify Alice is completely unaffected
    alice_reloaded = User.objects.get(pk=existing_user.pk)
    assert alice_reloaded.email == "alice@example.com"
    assert alice_reloaded.check_password("AlicePassword123!") is True
    assert not SocialAccount.objects.filter(user=alice_reloaded).exists()


@pytest.mark.django_db
def test_security_case_d_existing_user_unverified_google_email_rejected(rf, google_provider):
    """Scenario D: Prevent account takeover.

    If Google returns an unverified email matching an existing account, linking must be rejected with 400.
    """
    request = rf.get("/")
    adapter = get_adapter(request)

    target_user = User.objects.create_user(
        email="victim@example.com", password="VictimPassword123!"
    )

    # Attacker attempts OAuth login with victim's email where email_verified is False
    data = {
        "id": "google-attacker-uid-004",
        "email": "victim@example.com",
        "email_verified": False,
    }
    sociallogin = google_provider.sociallogin_from_response(request, data)

    with pytest.raises(ImmediateHttpResponse) as exc_info:
        adapter.pre_social_login(request, sociallogin)

    # Assert response is HTTP 400 Bad Request
    response = exc_info.value.response
    assert response.status_code == 400
    assert b"Cannot link account: The Google email is not verified by Google." in response.content

    # Target user must NOT be linked to the attacker's social account
    assert not SocialAccount.objects.filter(user=target_user).exists()
    assert target_user.check_password("VictimPassword123!") is True


@pytest.mark.django_db
def test_security_case_e_google_oauth_cancellation(client):
    """Scenario E: Google OAuth cancellation redirects to frontend login with error."""
    callback_url = reverse("google_callback")
    # Simulate user cancelling Google authorization screen
    response = client.get(f"{callback_url}?error=access_denied")

    assert response.status_code == 302
    assert response.headers["Location"].startswith(f"{settings.FRONTEND_URL}/login")
    assert "error=oauth_error" in response.headers["Location"]


@pytest.mark.django_db
def test_security_case_f_invalid_authorization_code(rf, google_provider):
    """Scenario F: Invalid or expired code exception triggers on_authentication_error redirect."""
    request = rf.get("/")
    adapter = get_adapter(request)

    with pytest.raises(ImmediateHttpResponse) as exc_info:
        adapter.on_authentication_error(
            request, google_provider, exception=OAuth2Error("Invalid authorization code")
        )

    response = exc_info.value.response
    assert response.status_code == 302
    assert response.headers["Location"] == f"{settings.FRONTEND_URL}/login?error=oauth_error"


@pytest.mark.django_db
def test_security_case_g_existing_google_socialaccount_login(rf, google_provider):
    """Scenario G: User with existing SocialAccount logs in again smoothly without error."""
    request = rf.get("/")
    adapter = get_adapter(request)

    user = User.objects.create_user(email="returning@example.com")
    SocialAccount.objects.create(user=user, provider="google", uid="google-returning-007")

    data = {
        "id": "google-returning-007",
        "email": "returning@example.com",
        "email_verified": True,
    }
    sociallogin = google_provider.sociallogin_from_response(request, data)
    sociallogin.lookup()

    assert sociallogin.is_existing is True
    assert sociallogin.user.pk == user.pk

    # pre_social_login should return early without modifying anything
    adapter.pre_social_login(request, sociallogin)
    assert SocialAccount.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_security_case_h_google_users_do_not_become_staff(rf, google_provider):
    """Scenario H: Verify social signups never gain is_staff or is_superuser permissions."""
    request = rf.get("/")
    adapter = get_adapter(request)

    data = {
        "id": "google-privilege-check-008",
        "email": "regulargoogle@example.com",
        "email_verified": True,
        "is_staff": True,
        "is_superuser": True,
    }
    sociallogin = google_provider.sociallogin_from_response(request, data)

    user = adapter.save_user(request, sociallogin)

    assert user.is_staff is False
    assert user.is_superuser is False


@pytest.mark.django_db
def test_security_case_i_teams_projects_permissions_preserved_after_linking(
    rf, google_provider, user, team
):
    """Scenario I: User's teams, project memberships, and roles remain intact after account linking."""
    request = rf.get("/")
    adapter = get_adapter(request)

    # Ensure a project exists for the team
    project = Project.objects.create(team=team, name="Production App")

    user_pk = user.pk
    team_pk = team.pk
    project_pk = project.pk

    # Google login with the user's verified email
    data = {
        "id": "google-team-owner-009",
        "email": user.email,
        "email_verified": True,
    }
    sociallogin = google_provider.sociallogin_from_response(request, data)
    adapter.pre_social_login(request, sociallogin)

    # Assert user identity is preserved
    assert user.pk == user_pk

    # Assert Team membership and role are preserved
    membership = TeamMember.objects.get(team_id=team_pk, user_id=user_pk)
    assert membership.role == "owner"

    # Assert Project access remains intact
    reloaded_project = Project.objects.get(pk=project_pk)
    assert reloaded_project.team.owner_id == user_pk


@pytest.mark.django_db
def test_google_login_redirect_url(client):
    """Verifies that GET /accounts/google/login/ initiates OAuth flow with correct parameters."""
    login_url = reverse("google_login")
    response = client.get(login_url)

    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "response_type=code" in location
    assert "email" in location and "profile" in location
    assert "accounts%2Fgoogle%2Flogin%2Fcallback%2F" in location
