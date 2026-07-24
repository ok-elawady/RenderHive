from django.urls import path

from .views import UserDetailView, UserListCreateView

app_name = "users"

urlpatterns = [
    path("users/", UserListCreateView.as_view(), name="user-list-create"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="user-detail"),
]
