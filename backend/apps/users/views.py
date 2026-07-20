from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["POST"])
@permission_classes([AllowAny])
def obtain_renderhive_token(request):
    """Authenticate a Django Admin-managed user and return a DRF token."""
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    user = authenticate(request, username=username, password=password)

    if user is None or not user.is_active:
        return Response(
            {"detail": "Invalid username or password. Please check your credentials."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    token, _ = Token.objects.get_or_create(user=user)
    display_name = user.get_full_name() or user.get_username()

    return Response(
        {
            "token": token.key,
            "user": {
                "id": user.pk,
                "username": user.get_username(),
                "display_name": display_name,
                "email": user.email,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            },
        }
    )
