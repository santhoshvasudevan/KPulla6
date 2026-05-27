"""Bridge Asset/MutualFundProfile rows to finance classification (Django allowed)."""

from __future__ import annotations

from finance.mutual_fund_classification import (
    MutualFundClassification,
    classify_mutual_fund,
    classification_fields_dict,
    is_explicit_primary_asset_class,
    storable_primary_asset_class,
)
from market_data.models import Asset, MutualFundProfile


def classify_mutual_fund_asset(
    asset: Asset,
    profile: MutualFundProfile | None,
) -> MutualFundClassification:
    return classify_mutual_fund(
        explicit_primary_asset_class=asset.primary_asset_class,
        scheme_category=profile.scheme_category if profile else "",
        scheme_type=profile.scheme_type if profile else "",
        scheme_name=profile.scheme_name if profile else asset.display_name,
    )


def maybe_apply_inferred_asset_class(
    asset: Asset,
    profile: MutualFundProfile,
) -> None:
    """Set Asset.primary_asset_class from profile metadata when not explicitly set."""
    if is_explicit_primary_asset_class(asset.primary_asset_class):
        return
    result = classify_mutual_fund_asset(asset, profile)
    stored = storable_primary_asset_class(result)
    if stored and asset.primary_asset_class != stored:
        asset.primary_asset_class = stored
        asset.save(update_fields=["primary_asset_class", "updated_at"])


def classification_fields_for_asset(
    asset: Asset,
    profile: MutualFundProfile | None,
) -> dict[str, str]:
    return classification_fields_dict(classify_mutual_fund_asset(asset, profile))
