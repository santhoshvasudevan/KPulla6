"""Pure mutual fund primary_asset_class inference (no Django imports)."""

from __future__ import annotations

from dataclasses import dataclass

# Stored on Asset.primary_asset_class (see market_data.models.PrimaryAssetClass)
CLASS_UNKNOWN = "UNKNOWN"
CLASS_EQUITY = "EQUITY"
CLASS_DEBT = "DEBT"
CLASS_HYBRID = "HYBRID"
CLASS_LIQUID = "LIQUID"  # cash-equivalent funds (overnight, liquid, money market)
CLASS_COMMODITY = "COMMODITY"
CLASS_OTHER = "OTHER"

SOURCE_EXPLICIT = "EXPLICIT"
SOURCE_INFERRED = "INFERRED"
SOURCE_UNKNOWN = "UNKNOWN"

_EXPLICIT_MISSING = frozenset({None, "", CLASS_UNKNOWN})

_HYBRID_KEYWORDS = (
    "hybrid",
    "balanced advantage",
    "aggressive hybrid",
    "conservative hybrid",
    "equity savings",
    "multi asset",
    "multi-asset",
    "dynamic asset allocation",
    "balanced hybrid",
)

_COMMODITY_KEYWORDS = (
    "gold",
    "silver",
    "commodity",
)

_CASH_EQUIV_KEYWORDS = (
    "liquid fund",
    "liquid direct",
    "overnight fund",
    " overnight",
    "money market",
    "money-market",
    "ultra short term",
)

_DEBT_KEYWORDS = (
    "debt",
    "gilt",
    "corporate bond",
    "dynamic bond",
    "banking & psu",
    "banking and psu",
    "short duration",
    "medium duration",
    "long duration",
    "ultra short",
    "credit risk",
    "income fund",
    "bond fund",
    "floater",
)

_EQUITY_KEYWORDS = (
    "equity",
    "large cap",
    "largecap",
    "mid cap",
    "midcap",
    "small cap",
    "smallcap",
    "flexi cap",
    "multi cap",
    "elss",
    "index fund",
    "sectoral",
    "thematic",
    "focused",
    "value fund",
    "contra",
)

_INTERNATIONAL_KEYWORDS = (
    "international",
    "global",
    "nasdaq",
    "s&p 500",
    "s and p 500",
    " us equity",
    " us fund",
    "foreign",
    "overseas",
)


@dataclass(frozen=True)
class MutualFundClassification:
    primary_asset_class: str
    classification_source: str
    classification_notes: str = ""


def _normalized(value: str | None) -> str:
    return (value or "").strip()


def _haystack(*, scheme_category: str, scheme_type: str, scheme_name: str) -> str:
    return " ".join(
        (
            _normalized(scheme_category),
            _normalized(scheme_type),
            _normalized(scheme_name),
        )
    ).lower()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(k in text for k in keywords)


def is_explicit_primary_asset_class(value: str | None) -> bool:
    """True when Asset.primary_asset_class should not be overwritten by inference."""
    if value is None:
        return False
    normalized = _normalized(value).upper()
    return normalized not in _EXPLICIT_MISSING


def classify_mutual_fund(
    *,
    explicit_primary_asset_class: str | None,
    scheme_category: str = "",
    scheme_type: str = "",
    scheme_name: str = "",
) -> MutualFundClassification:
    """
    Resolve MVP classification for a mutual fund.

    Explicit stored class wins. Inference is conservative and metadata-only.
    Hybrid funds map to HYBRID, never to EQUITY.
    """
    explicit = _normalized(explicit_primary_asset_class).upper() or None
    if is_explicit_primary_asset_class(explicit):
        return MutualFundClassification(
            primary_asset_class=explicit,  # type: ignore[arg-type]
            classification_source=SOURCE_EXPLICIT,
            classification_notes="",
        )

    text = _haystack(
        scheme_category=scheme_category,
        scheme_type=scheme_type,
        scheme_name=scheme_name,
    )
    if not text.strip():
        return MutualFundClassification(
            primary_asset_class=CLASS_UNKNOWN,
            classification_source=SOURCE_UNKNOWN,
            classification_notes="Insufficient scheme metadata for classification",
        )

    if _contains_any(text, _HYBRID_KEYWORDS):
        return MutualFundClassification(
            primary_asset_class=CLASS_HYBRID,
            classification_source=SOURCE_INFERRED,
            classification_notes="Inferred from scheme metadata (hybrid)",
        )

    if _contains_any(text, _COMMODITY_KEYWORDS):
        return MutualFundClassification(
            primary_asset_class=CLASS_COMMODITY,
            classification_source=SOURCE_INFERRED,
            classification_notes="Inferred from scheme metadata (commodity)",
        )

    if _contains_any(text, _CASH_EQUIV_KEYWORDS):
        return MutualFundClassification(
            primary_asset_class=CLASS_LIQUID,
            classification_source=SOURCE_INFERRED,
            classification_notes="Inferred as cash-equivalent (LIQUID)",
        )

    if _contains_any(text, _DEBT_KEYWORDS):
        return MutualFundClassification(
            primary_asset_class=CLASS_DEBT,
            classification_source=SOURCE_INFERRED,
            classification_notes="Inferred from scheme metadata (debt)",
        )

    if _contains_any(text, _INTERNATIONAL_KEYWORDS):
        return MutualFundClassification(
            primary_asset_class=CLASS_EQUITY,
            classification_source=SOURCE_INFERRED,
            classification_notes=(
                "International/global fund classified as EQUITY; "
                "region/exposure breakdown deferred"
            ),
        )

    if _contains_any(text, _EQUITY_KEYWORDS):
        return MutualFundClassification(
            primary_asset_class=CLASS_EQUITY,
            classification_source=SOURCE_INFERRED,
            classification_notes="Inferred from scheme metadata (equity)",
        )

    return MutualFundClassification(
        primary_asset_class=CLASS_UNKNOWN,
        classification_source=SOURCE_UNKNOWN,
        classification_notes="Could not infer class from scheme metadata",
    )


def classification_fields_dict(result: MutualFundClassification) -> dict[str, str]:
    """API-safe dict for holdings/asset detail."""
    payload: dict[str, str] = {
        "primary_asset_class": result.primary_asset_class,
        "classification_source": result.classification_source,
    }
    if result.classification_notes:
        payload["classification_notes"] = result.classification_notes
    return payload


def storable_primary_asset_class(result: MutualFundClassification) -> str | None:
    """Value safe to persist on Asset when inferring (excludes UNKNOWN)."""
    if result.classification_source != SOURCE_INFERRED:
        return None
    if result.primary_asset_class == CLASS_UNKNOWN:
        return None
    return result.primary_asset_class
