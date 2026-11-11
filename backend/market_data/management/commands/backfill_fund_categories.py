from django.core.management.base import BaseCommand

from market_data.models import MutualFundProfile
from market_data.providers.mutual_fund_nav_provider import AmfiNavProvider
from market_data.services.fund_categories import category_changes, category_pair, fill_categories, has_missing_metadata


class Command(BaseCommand):
    help = "Preview scheme category updates. Use --apply only after reviewing and backing up."

    def add_arguments(self, parser):
        parser.add_argument("--scheme-code", action="append")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        profiles = MutualFundProfile.objects.order_by("scheme_code")
        if options["scheme_code"]:
            profiles = profiles.filter(scheme_code__in=options["scheme_code"])
        provider = AmfiNavProvider()
        for profile in profiles.iterator():
            if not has_missing_metadata(profile):
                self.stdout.write(f"{profile.scheme_code}: existing={profile.scheme_category!r}, skipped (already populated)")
                continue
            try:
                metadata = provider.get_category_metadata(profile.scheme_code)
            except Exception:
                self.stdout.write(f"{profile.scheme_code}: existing={profile.scheme_category!r}, skipped (provider unavailable)")
                continue
            updates, conflicts = category_changes(profile, metadata)
            category, subcategory = category_pair((metadata or {}).get("scheme_category"))
            self.stdout.write(
                f"{profile.scheme_code}: existing={profile.scheme_category!r}, "
                f"category={category!r}, subcategory={subcategory!r}, "
                f"fund_house={profile.fund_house!r} → {updates.get('fund_house', profile.fund_house)!r}, "
                f"updates={', '.join(updates) or 'none'}, conflicts={', '.join(conflicts) or 'none'}"
                + (" (missing or mismatched metadata)" if not metadata else
                   " (no eligible changes)" if not updates and not conflicts else "")
            )
            if options["apply"]:
                fill_categories(profile, metadata)
