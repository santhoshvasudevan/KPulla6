import os
import sys

from django.apps import AppConfig
from django.db.models.signals import post_migrate


def sync_site_from_env() -> None:
    domain = os.environ.get("DJANGO_SITE_DOMAIN", "").strip()
    if not domain:
        return
    from django.conf import settings
    from django.contrib.sites.models import Site
    from django.db import OperationalError

    name = os.environ.get("DJANGO_SITE_NAME", domain).strip() or domain
    try:
        Site.objects.update_or_create(
            pk=settings.SITE_ID,
            defaults={"domain": domain, "name": name},
        )
    except OperationalError:
        pass


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self) -> None:
        post_migrate.connect(
            self._on_post_migrate, sender=self, dispatch_uid="accounts.sync_site"
        )
        if "pytest" not in sys.modules:
            sync_site_from_env()

    def _on_post_migrate(self, sender, **kwargs) -> None:
        sync_site_from_env()
