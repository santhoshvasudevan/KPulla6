"""Provider category normalization and safe fill-only updates."""

import re

from market_data.models import MutualFundProfile

FIELDS = {"scheme_category": 255, "scheme_type": 128}


def category_pair(raw):
    parts = re.split(r"\s+[-–—]\s+", raw.strip() if isinstance(raw, str) else "", maxsplit=1)
    category = re.sub(r"\s+Scheme$", "", parts[0], flags=re.IGNORECASE).strip()
    return category, parts[1].strip() if len(parts) > 1 else ""


def category_changes(profile, metadata):
    updates, conflicts = {}, []
    for field, limit in FIELDS.items():
        value = (metadata or {}).get(field)
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            continue
        existing = getattr(profile, field).strip()
        if not existing:
            updates[field] = value.strip()
        elif existing != value.strip():
            conflicts.append(field)
    return updates, conflicts


def fill_categories(profile, metadata):
    updates, conflicts = category_changes(profile, metadata)
    written = 0
    for field, value in updates.items():
        written += MutualFundProfile.objects.filter(
            pk=profile.pk, **{field: getattr(profile, field)}
        ).update(**{field: value, f"{field}_from_provider": True})
    return written, conflicts
