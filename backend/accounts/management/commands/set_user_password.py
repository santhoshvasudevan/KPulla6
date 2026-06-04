import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = "Set or reset a user's password from INITIAL_USER_PASSWORD env var or --password."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default="santhoshkgvasudevan@gmail.com",
            help="User email (default: initial owner email).",
        )
        parser.add_argument(
            "--password",
            default=None,
            help="New password. If omitted, uses INITIAL_USER_PASSWORD from the environment.",
        )

    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()
        password = options["password"] or os.environ.get("INITIAL_USER_PASSWORD")
        if not password:
            raise CommandError(
                "Provide --password or set INITIAL_USER_PASSWORD in the environment."
            )
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            raise CommandError(f"No user found with email: {email}")
        user.set_password(password)
        user.save(update_fields=["password"])
        self.stdout.write(self.style.SUCCESS(f"Password updated for {user.email}"))
