import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

pytestmark = pytest.mark.django_db


class TestHeadlessAuthentication:
    @pytest.fixture
    def api_client(self):
        return APIClient()

    @pytest.fixture
    def test_user(self):
        user = User.objects.create_user(username="testuser", password="password123")
        return user

    def test_login_endpoint_returns_success(self, api_client, test_user):
        """Test that the headless login endpoint works with valid credentials."""
        # The allauth headless browser login endpoint
        url = "/_allauth/browser/v1/auth/login"

        response = api_client.post(url, data={"username": "testuser", "password": "password123"}, format="json")

        assert response.status_code == 200
        # allauth headless returns a status code 200 with meta/data payload
        assert "data" in response.json()

    def test_login_endpoint_fails_with_invalid_credentials(self, api_client, test_user):
        """Test that headless login fails with incorrect password."""
        url = "/_allauth/browser/v1/auth/login"

        response = api_client.post(url, data={"username": "testuser", "password": "wrongpassword"}, format="json")

        assert response.status_code == 400

    def test_session_token_authentication_protects_endpoints(self, api_client, test_user):
        """Test that a protected endpoint requires authentication, and works with session."""
        # /api/jobs/ is protected by IsAuthenticated
        url = "/api/jobs/"

        # 1. Unauthenticated request should fail
        response_unauth = api_client.get(url)
        assert response_unauth.status_code in [401, 403]

        # 2. Login
        login_response = api_client.post(
            "/_allauth/browser/v1/auth/login", data={"username": "testuser", "password": "password123"}, format="json"
        )
        assert login_response.status_code == 200

        # In browser mode, allauth sets a session cookie, so the api_client
        # should now have the session cookie and CSRF configured (if DRF enforces it).
        # Actually APIClient bypasses CSRF for tests unless enforce_csrf_checks=True.
        # Let's verify the protected endpoint is now accessible.
        response_auth = api_client.get(url)
        assert response_auth.status_code == 200
