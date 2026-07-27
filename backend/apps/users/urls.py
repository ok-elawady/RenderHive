from django.urls import path

from .views import UserDetailView, UserListCreateView, UserPasswordResetView

app_name = "users"

urlpatterns = [
    path("users/", UserListCreateView.as_view(), name="user-list-create"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="user-detail"),
    path("users/<int:pk>/password/", UserPasswordResetView.as_view(), name="user-password-reset"),
]
