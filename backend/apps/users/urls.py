from django.urls import path

from .views import PasswordChangeView

urlpatterns = [
    path("password/change/", PasswordChangeView.as_view(), name="password-change"),
]
