from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.oauth_urls")),
    path("accounts/", include("allauth.urls")),
    path("api/v1/", include("api.urls")),
]
