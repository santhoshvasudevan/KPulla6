from django.urls import path

from accounts.views import (
    CsrfView,
    CurrentUserView,
    LoginView,
    LogoutView,
    PasswordResetRequestView,
    RegisterView,
)

urlpatterns = [
    path("csrf", CsrfView.as_view(), name="auth-csrf"),
    path("me", CurrentUserView.as_view(), name="auth-me"),
    path("login", LoginView.as_view(), name="auth-login"),
    path("logout", LogoutView.as_view(), name="auth-logout"),
    path("register", RegisterView.as_view(), name="auth-register"),
    path("password-reset", PasswordResetRequestView.as_view(), name="auth-password-reset"),
]
