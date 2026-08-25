import pytest
from django.urls import reverse
from rest_framework import status
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress

User = get_user_model()

@pytest.mark.django_db
class TestAuthenticationAPI:
    def test_registration_creates_user_but_not_team(self, client):
        url = reverse("api:rest_register")
        data = {
            "email": "newuser@example.com",
            "password1": "SecurePass123",
            "password2": "SecurePass123",
        }
        
        response = client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify user created
        user = User.objects.get(email="newuser@example.com")
        assert not user.is_staff
        
        # Verify email address instance created (unverified)
        email_obj = EmailAddress.objects.get(user=user, email="newuser@example.com")
        assert not email_obj.verified
        
        # Verify no team was automatically created (assuming Keel's models)
        from apps.teams.models import Team
        assert Team.objects.filter(owner=user).count() == 0

    def test_registration_duplicate_email(self, client, user):
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        url = reverse("api:rest_register")
        data = {
            "email": user.email, # Duplicate
            "password1": "SecurePass123",
            "password2": "SecurePass123",
        }
        
        response = client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["status"] == "error"
        assert "e-mail" in response.data["message"]

    def test_login_success_and_session_persistence(self, client, user):
        # By default in allauth tests, users may not have verified emails.
        # Ensure email is verified if required.
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        user.set_password("testpass123")
        user.save()
        
        url = reverse("api:rest_login")
        data = {
            "email": user.email,
            "password": "testpass123"
        }
        
        response = client.post(url, data)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Check session cookie exists
        assert client.session.session_key is not None
        
        # Verify session persistence by calling user details endpoint
        user_url = reverse("api:rest_user_details")
        user_response = client.get(user_url)
        assert user_response.status_code == status.HTTP_200_OK
        assert user_response.data["email"] == user.email

    def test_login_unverified_email_fails(self, client, user):
        # Delete any verified email address
        EmailAddress.objects.filter(user=user).delete()
        EmailAddress.objects.create(user=user, email=user.email, verified=False, primary=True)
        
        user.set_password("testpass123")
        user.save()
        
        url = reverse("api:rest_login")
        data = {
            "email": user.email,
            "password": "testpass123"
        }
        
        response = client.post(url, data)
        # Should fail due to ACCOUNT_EMAIL_VERIFICATION = "mandatory"
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout(self, client, user):
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        user.set_password("testpass123")
        user.save()
        
        # Login
        client.post(reverse("api:rest_login"), {"email": user.email, "password": "testpass123"})
        assert client.session.session_key is not None
        
        # Logout
        url = reverse("api:rest_logout")
        response = client.post(url)
        assert response.status_code == status.HTTP_200_OK
        
        # Verify user endpoint fails after logout
        user_response = client.get(reverse("api:rest_user_details"))
        assert user_response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
