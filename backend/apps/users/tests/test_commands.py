import os
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from rest_framework.authtoken.models import Token

User = get_user_model()

pytestmark = pytest.mark.django_db


class TestCreateFarmTokenCommand:
    def test_creates_group_user_and_token(self):
        """Test that the command creates the required group, user, and token."""
        assert not Group.objects.filter(name="farm_agents").exists()
        assert not User.objects.filter(username="farm_service").exists()

        call_command("create_farm_token")

        assert Group.objects.filter(name="farm_agents").exists()
        user = User.objects.get(username="farm_service")
        assert user.groups.filter(name="farm_agents").exists()
        assert Token.objects.filter(user=user).exists()
        assert not user.has_usable_password()

    def test_idempotency(self):
        """Test that running the command multiple times does not duplicate or break things."""
        call_command("create_farm_token")
        token_1 = Token.objects.get(user__username="farm_service").key

        # Run again
        call_command("create_farm_token")
        token_2 = Token.objects.get(user__username="farm_service").key

        # The token should not change if not forced by env
        assert token_1 == token_2

    @mock.patch.dict(os.environ, {"FARM_AGENT_TOKEN": "fixed_token_123"})
    def test_uses_env_variable_for_token(self):
        """Test that the token is set to the env variable if provided."""
        call_command("create_farm_token")

        token = Token.objects.get(user__username="farm_service")
        assert token.key == "fixed_token_123"

    def test_updates_existing_token_from_env(self):
        """Test that an existing token gets updated to match the env variable."""
        # First run without env var
        if "FARM_AGENT_TOKEN" in os.environ:
            del os.environ["FARM_AGENT_TOKEN"]

        call_command("create_farm_token")
        user = User.objects.get(username="farm_service")
        old_token = Token.objects.get(user=user)
        assert old_token.key != "new_fixed_token_456"

        # Run again with env var mocked
        with mock.patch.dict(os.environ, {"FARM_AGENT_TOKEN": "new_fixed_token_456"}):
            call_command("create_farm_token")

        new_token = Token.objects.get(user=user)
        assert new_token.key == "new_fixed_token_456"
