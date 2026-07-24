import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

User = get_user_model()

pytestmark = pytest.mark.django_db


def authenticated_client(user):
    client = APIClient()
    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


def test_superuser_can_list_active_users():
    admin = User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="StrongPass!234",
    )
    User.objects.create_user(username="artist", password="StrongPass!234")

    response = authenticated_client(admin).get("/api/users/")

    assert response.status_code == 200
    assert {user["username"] for user in response.json()} == {"admin", "artist"}


def test_staff_user_cannot_access_user_administration():
    staff = User.objects.create_user(
        username="staff",
        password="StrongPass!234",
        is_staff=True,
    )

    response = authenticated_client(staff).get("/api/users/")

    assert response.status_code == 403


def test_superuser_can_create_user_with_hashed_password_and_role():
    admin = User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="StrongPass!234",
    )
    payload = {
        "first_name": "Nora",
        "last_name": "Ali",
        "username": "nora.fx",
        "email": "nora@example.com",
        "title_role": "FX Artist",
        "access_level": "Staff",
        "password": "AnotherStrongPass!234",
    }

    response = authenticated_client(admin).post(
        "/api/users/",
        payload,
        format="json",
    )

    assert response.status_code == 201
    created_user = User.objects.get(username="nora.fx")
    assert created_user.check_password(payload["password"])
    assert created_user.is_staff is True
    assert created_user.is_superuser is False
    assert created_user.groups.filter(name="FX Artist").exists()


def test_superuser_can_update_and_delete_another_user():
    admin = User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="StrongPass!234",
    )
    artist = User.objects.create_user(
        username="artist",
        email="artist@example.com",
        password="StrongPass!234",
    )
    client = authenticated_client(admin)

    update_response = client.patch(
        f"/api/users/{artist.pk}/",
        {
            "first_name": "Updated",
            "last_name": "Artist",
            "email": "updated.artist@example.com",
            "title_role": "Lighting Lead",
            "access_level": "Staff",
        },
        format="json",
    )

    assert update_response.status_code == 200
    artist.refresh_from_db()
    assert artist.first_name == "Updated"
    assert artist.is_staff is True
    assert artist.groups.filter(name="Lighting Lead").exists()

    # True partial update test (no title_role or access_level)
    partial_update_response = client.patch(
        f"/api/users/{artist.pk}/",
        {"first_name": "PartialUpdateName"},
        format="json",
    )
    
    assert partial_update_response.status_code == 200
    artist.refresh_from_db()
    assert artist.first_name == "PartialUpdateName"
    assert artist.is_staff is True  # Did not lose previous staff access

    delete_response = client.delete(f"/api/users/{artist.pk}/")

    assert delete_response.status_code == 204
    artist.refresh_from_db()
    assert not artist.is_active


def test_superuser_cannot_delete_own_account():
    admin = User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="StrongPass!234",
    )

    response = authenticated_client(admin).delete(f"/api/users/{admin.pk}/")

    assert response.status_code == 400
    admin.refresh_from_db()
    assert admin.is_active
