from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.services import is_registration_incomplete

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name")
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    username_or_email = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)
    password_confirm = serializers.CharField(trim_whitespace=False)

    def validate_username(self, value):
        username = value.strip()
        if not username:
            raise serializers.ValidationError("Username must not be empty.")
        user = User.objects.filter(username__iexact=username).first()
        if user:
            if is_registration_incomplete(user):
                self.context["_incomplete_user"] = user
                return username
            raise serializers.ValidationError("A user with that username already exists.")
        return username

    def validate_email(self, value):
        email = value.strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if user:
            incomplete = self.context.get("_incomplete_user")
            if is_registration_incomplete(user):
                if incomplete is not None and incomplete.pk != user.pk:
                    raise serializers.ValidationError("A user with that email already exists.")
                self.context["_incomplete_user"] = user
                return email
            raise serializers.ValidationError("A user with that email already exists.")
        return email

    def validate(self, attrs):
        password = attrs.get("password")
        password_confirm = attrs.get("password_confirm")
        if password != password_confirm:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        incomplete_user = self.context.get("_incomplete_user")
        try:
            validate_password(password, user=incomplete_user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
