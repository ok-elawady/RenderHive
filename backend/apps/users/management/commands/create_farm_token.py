"""
Management command to bootstrap the shared farm service account and API token.

Run once per environment (dev, staging, production) by a sysadmin:

    uv run python manage.py create_farm_token

Output the token and instruct the operator to write it to renderhive.conf in
the shared network config directory. Worker daemons and DCC plugins read this
file at startup and attach the token to every API request.
"""

import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from rest_framework.authtoken.models import Token

User = get_user_model()

FARM_USERNAME = "farm_service"
FARM_GROUP = "farm_agents"


class Command(BaseCommand):
    """Bootstrap the farm_service user and generate its shared API token.

    Creates the ``farm_agents`` group (if it does not exist), creates the
    ``farm_service`` system user (if it does not exist), adds it to the group,
    and creates or retrieves its DRF ``Token``.

    The emitted token value should be placed in the shared network config file::

        # /proj/configs/renderhive/renderhive.conf
        RENDERHIVE_API_URL=http://renderhive.studio.local:8000
        RENDERHIVE_API_TOKEN=<token>

    Outputs the token to stdout so the operator can record it.
    """

    help = "Bootstrap the farm_service user and generate the shared studio API token."

    def handle(self, *args, **options):
        """Execute the command.

        Args:
            *args: Positional arguments (unused).
            **options: Keyword options from the argument parser.
        """
        # Create or get the farm_agents group
        group, group_created = Group.objects.get_or_create(name=FARM_GROUP)
        if group_created:
            self.stdout.write(self.style.SUCCESS(f"Created group: '{FARM_GROUP}'"))
        else:
            self.stdout.write(f"Group '{FARM_GROUP}' already exists.")

        # Create or get the farm_service user
        user, user_created = User.objects.get_or_create(
            username=FARM_USERNAME,
            defaults={
                "is_active": True,
                "is_staff": False,
                "is_superuser": False,
                "email": "farm_service@renderhive.internal",
            },
        )
        if user_created:
            user.set_unusable_password()
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created user: '{FARM_USERNAME}'"))
        else:
            self.stdout.write(f"User '{FARM_USERNAME}' already exists.")

        # Add the user to the farm_agents group
        user.groups.add(group)

        # Create or retrieve the DRF auth token
        token, token_created = Token.objects.get_or_create(user=user)

        env_token = os.environ.get("FARM_AGENT_TOKEN")
        if env_token:
            if token.key != env_token:
                Token.objects.filter(user=user).update(key=env_token)
                token.key = env_token
                self.stdout.write(self.style.SUCCESS("Updated API token from FARM_AGENT_TOKEN environment variable."))
            else:
                self.stdout.write("Existing token matches FARM_AGENT_TOKEN.")
        elif token_created:
            self.stdout.write(self.style.SUCCESS("Generated new API token."))
        else:
            self.stdout.write("Existing token retrieved.")

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("═" * 60))
        self.stdout.write(self.style.WARNING("  FARM API TOKEN (add to renderhive.conf)"))
        self.stdout.write(self.style.WARNING("═" * 60))
        self.stdout.write(f"  RENDERHIVE_API_TOKEN={token.key}")
        self.stdout.write(self.style.WARNING("═" * 60))
        self.stdout.write("")
        self.stdout.write(
            "  Workers and DCC plugins must include this token in every request:\n  Authorization: Token <token>"
        )
