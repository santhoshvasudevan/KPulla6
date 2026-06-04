from __future__ import annotations

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from portfolios.seed import ensure_default_portfolio
from settings_app.seed import ensure_app_settings

User = get_user_model()

INITIAL_OWNER_EMAIL = "santhoshkgvasudevan@gmail.com"


def get_or_create_initial_owner() -> User:
    user = User.objects.filter(email__iexact=INITIAL_OWNER_EMAIL).first()
    if user:
        return user
    username = INITIAL_OWNER_EMAIL.split("@")[0]
    base_username = username
    suffix = 1
    while User.objects.filter(username__iexact=username).exists():
        username = f"{base_username}{suffix}"
        suffix += 1
    return User.objects.create_user(
        username=username,
        email=INITIAL_OWNER_EMAIL,
        is_active=True,
    )


def authenticate_username_or_email(*, username_or_email: str, password: str):
    identifier = (username_or_email or "").strip()
    if not identifier:
        return None
    user = authenticate(username=identifier, password=password)
    if user is not None:
        return user
    matched = User.objects.filter(email__iexact=identifier).first()
    if matched is None:
        return None
    return authenticate(username=matched.username, password=password)


def register_user(*, username: str, email: str, password: str) -> User:
    user = User.objects.create_user(
        username=username.strip(),
        email=email.strip().lower(),
        password=password,
    )
    ensure_default_portfolio(user)
    ensure_app_settings(user)
    return user


def request_password_reset(*, email: str) -> dict:
    normalized = email.strip().lower()
    user = User.objects.filter(email__iexact=normalized).first()
    email_backend = getattr(settings, "EMAIL_BACKEND", "")
    email_configured = email_backend and "console" not in email_backend.lower()

    if user is None:
        return {
            "detail": "If an account exists for that email, password reset instructions were sent.",
            "email_sent": False,
        }

    if not email_configured:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return {
            "detail": (
                "Email backend is not configured for production mail delivery. "
                "Use the management command `set_user_password` for local password resets, "
                "or configure Django EMAIL_* settings."
            ),
            "email_sent": False,
            "dev_reset_path": f"/api/v1/auth/password-reset/confirm?uid={uid}&token={token}",
        }

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?uid={uid}&token={token}"
    send_mail(
        subject="Portfolio Insight password reset",
        message=f"Use this link to reset your password: {reset_url}",
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@localhost"),
        recipient_list=[user.email],
        fail_silently=False,
    )
    return {
        "detail": "If an account exists for that email, password reset instructions were sent.",
        "email_sent": True,
    }
