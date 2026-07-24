from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response

from .models import User
from .permissions import IsSuperUser
from .serializers import (
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
    UserPasswordResetSerializer,
)


class UserListCreateView(ListCreateAPIView):
    permission_classes = [IsSuperUser]
    pagination_class = None

    def get_queryset(self):
        return User.objects.filter(is_active=True).prefetch_related("groups").order_by("username")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UserCreateSerializer
        return UserSerializer


class UserDetailView(RetrieveUpdateDestroyAPIView):
    queryset = User.objects.filter(is_active=True).prefetch_related("groups")
    permission_classes = [IsSuperUser]

    def get_serializer_class(self):
        if self.request.method in {"PUT", "PATCH"}:
            return UserUpdateSerializer
        return UserSerializer

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user.pk == request.user.pk:
            raise ValidationError({"detail": "You cannot delete your own account."})
        if user.is_superuser and User.objects.filter(is_active=True, is_superuser=True).count() <= 1:
            raise ValidationError({"detail": "The final active superuser cannot be deleted."})

        user.is_active = False
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserPasswordResetView(RetrieveUpdateDestroyAPIView):
    """
    Dedicated view for Superusers to reset any user's password.
    Inherits from RetrieveUpdateDestroyAPIView to match UserDetailView behavior 
    but restricts the serializer to only handle password updates.
    """
    queryset = User.objects.filter(is_active=True)
    permission_classes = [IsSuperUser]
    serializer_class = UserPasswordResetSerializer

    def get(self, request, *args, **kwargs):
        # We don't want to support GET on the password endpoint
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def delete(self, request, *args, **kwargs):
        # We don't want to support DELETE on the password endpoint
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
