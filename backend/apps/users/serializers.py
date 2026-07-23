from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

User = get_user_model()

TITLE_ROLE_CHOICES = (
    ("Technical Director", "Technical Director"),
    ("Animator", "Animator"),
    ("Pipeline Engineer", "Pipeline Engineer"),
    ("FX Artist", "FX Artist"),
    ("Lighting Lead", "Lighting Lead"),
)

ACCESS_LEVEL_CHOICES = (
    ("Superuser", "Superuser"),
    ("Staff", "Staff"),
    ("Client", "Client"),
)


class AdminUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    title_role = serializers.SerializerMethodField()
    access_level = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "full_name",
            "username",
            "email",
            "title_role",
            "access_level",
            "is_active",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
        )
        read_only_fields = fields

    def get_full_name(self, user):
        return user.get_full_name().strip() or user.username

    def get_title_role(self, user):
        group = next(iter(user.groups.all()), None)
        if group:
            return group.name
        if user.is_superuser:
            return "Technical Director"
        return "Render User"

    def get_access_level(self, user):
        if user.is_superuser:
            return "Superuser"
        if user.is_staff:
            return "Staff"
        return "Client"


class AdminUserCreateSerializer(serializers.ModelSerializer):
    title_role = serializers.ChoiceField(choices=TITLE_ROLE_CHOICES)
    access_level = serializers.ChoiceField(choices=ACCESS_LEVEL_CHOICES)
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "username",
            "email",
            "title_role",
            "access_level",
            "password",
        )

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate(self, attrs):
        candidate = User(
            username=attrs.get("username", ""),
            email=attrs.get("email", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": list(error.messages)}) from error
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        title_role = validated_data.pop("title_role")
        access_level = validated_data.pop("access_level")
        password = validated_data.pop("password")
        is_superuser = access_level == "Superuser"
        is_staff = access_level in {"Superuser", "Staff"}

        user = User.objects.create_user(
            **validated_data,
            password=password,
            is_staff=is_staff,
            is_superuser=is_superuser,
            is_active=True,
        )
        group, _ = Group.objects.get_or_create(name=title_role)
        user.groups.set([group])
        return user

    def to_representation(self, instance):
        return AdminUserSerializer(instance, context=self.context).data


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    title_role = serializers.ChoiceField(choices=TITLE_ROLE_CHOICES)
    access_level = serializers.ChoiceField(choices=ACCESS_LEVEL_CHOICES)

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "title_role",
            "access_level",
        )

    def validate_email(self, value):
        email = value.strip().lower()
        if not email:
            return email
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate_access_level(self, value):
        request = self.context.get("request")
        if request and self.instance == request.user and value != "Superuser":
            raise serializers.ValidationError("You cannot remove your own superuser access.")
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        title_role = validated_data.pop("title_role")
        access_level = validated_data.pop("access_level")
        instance.is_superuser = access_level == "Superuser"
        instance.is_staff = access_level in {"Superuser", "Staff"}

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()
        group, _ = Group.objects.get_or_create(name=title_role)
        instance.groups.set([group])
        return instance

    def to_representation(self, instance):
        return AdminUserSerializer(instance, context=self.context).data
