from django.urls import path

from allauth.socialaccount.providers.oauth2.views import (
    OAuth2CallbackView,
    OAuth2LoginView,
)

from accounts.google_oauth import KPulla6GoogleOAuth2Adapter

urlpatterns = [
    path(
        "google/login/",
        OAuth2LoginView.adapter_view(KPulla6GoogleOAuth2Adapter),
        name="google_login",
    ),
    path(
        "google/login/callback/",
        OAuth2CallbackView.adapter_view(KPulla6GoogleOAuth2Adapter),
        name="google_callback",
    ),
]
