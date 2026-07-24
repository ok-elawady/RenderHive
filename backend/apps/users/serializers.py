from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

User = get_user_model()

TITLE_ROLE_CHOICES = (
    ("Technical Director", "Technical Director"),
    ("Animator", "Animator"),
    ("Pipeline Engineer", "Pipeline Engineer"),
    ("FX Artist", "FX Artist"),
    ("Lighting Lead", "Lighting Lead"),
    ("Render User", "Render User"),
)

ACCESS_LEVEL_CHOICES = (
    ("Superuser", "Superuser"),
    ("Staff", "Staff"),
    ("Client", "Client"),
)


class UserSerializer(serializers.ModelSerializer):
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


class UserCreateSerializer(serializers.ModelSerializer):
    title_role = serializers.ChoiceField(choices=TITLE_ROLE_CHOICES)
    access_level = serializers.ChoiceField(choices=ACCESS_LEVEL_CHOICES)
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all(), lookup='iexact')]
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
        return UserSerializer(instance, context=self.context).data


class UserUpdateSerializer(serializers.ModelSerializer):
    title_role = serializers.ChoiceField(choices=TITLE_ROLE_CHOICES)
    access_level = serializers.ChoiceField(choices=ACCESS_LEVEL_CHOICES)
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all(), lookup='iexact')]
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "title_role",
            "access_level",
        )

    def validate_access_level(self, value):
        request = self.context.get("request")
        if request and self.instance == request.user and value != "Superuser":
            raise serializers.ValidationError("You cannot remove your own superuser access.")
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        title_role = validated_data.pop("title_role", None)
        access_level = validated_data.pop("access_level", None)
        
        if access_level:
            instance.is_superuser = access_level == "Superuser"
            instance.is_staff = access_level in {"Superuser", "Staff"}

        if title_role:
            group, _ = Group.objects.get_or_create(name=title_role)
            instance.groups.set([group])
            
        instance.save()
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        return UserSerializer(instance, context=self.context).data
