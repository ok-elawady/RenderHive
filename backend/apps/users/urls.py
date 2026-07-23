from django.urls import path

from .views import AdminUserDetailView, AdminUserListCreateView

app_name = "users"

urlpatterns = [
    path("users/", AdminUserListCreateView.as_view(), name="admin-user-list-create"),
    path("users/<int:pk>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
]
