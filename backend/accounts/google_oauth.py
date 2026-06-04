"""Google OAuth adapter with a stable callback URL for local dev (Vite proxy)."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest

from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter


class KPulla6GoogleOAuth2Adapter(GoogleOAuth2Adapter):
    """Use a fixed redirect URI so authorize + token exchange always match."""

    def get_callback_url(self, request: HttpRequest, app: SocialApp) -> str:
        callback_url = getattr(settings, "GOOGLE_OAUTH_CALLBACK_URL", "").strip()
        if callback_url:
            return callback_url
        return super().get_callback_url(request, app)
