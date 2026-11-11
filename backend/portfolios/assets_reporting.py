"""Read models for Assets allocation and mutual fund breakdowns."""

from collections import Counter, defaultdict
from decimal import Decimal

from market_data.models import PersonalFundCategory
from market_data.services.fund_categories import category_pair


def _value(rows):
    values = [row["display_current_value"] for row in rows]
    if any(value is None for value in values):
        return None
    return sum((Decimal(str(value)) for value in values), Decimal("0"))


def _weight(value, total):
    return float(value / total) if value is not None and total else None


def _allocation(rows, *, by_folio=False):
    groups = defaultdict(list)
    for row in rows:
        if row["display_current_value"] is None or row["display_current_value"] <= 0:
            continue
        asset_type = row.get("asset_type", "STOCK")
        key = row.get("holding_key") or row["asset_symbol"]
        if asset_type == "MUTUAL_FUND" and not by_folio:
            key = row["scheme_code"]
        groups[(asset_type, key)].append(row)
    total = _value([row for group in groups.values() for row in group])
    slices = []
    for (asset_type, key), group in groups.items():
        first = group[0]
        name = first.get("scheme_name") or first.get("asset_name") or first.get("institution_name") or first["asset_symbol"]
        if asset_type == "MUTUAL_FUND" and by_folio:
            name = f'{name} · Folio {first["folio_number"]}'
        value = _value(group)
        slices.append({
            "id": f"{asset_type}:{key}",
            "name": name,
            "value": float(value),
            "weight": _weight(value, total),
            "holding_keys": [row.get("holding_key") or row["asset_symbol"] for row in group],
        })
    labels = Counter(slice_["name"] for slice_ in slices)
    for slice_ in slices:
        if labels[slice_["name"]] > 1:
            slice_["name"] += f' · {slice_["id"].split(":", 1)[1]}'
    return sorted(slices, key=lambda row: (-row["value"], row["id"]))


def _fund_stats(rows, total):
    value = _value(rows)
    return {
        "value": float(value) if value is not None else None,
        "weight": _weight(value, total),
        "scheme_count": len({row["scheme_code"] for row in rows}),
    }


def _folio_count(rows):
    # One investor folio can hold several schemes from the same fund house.
    return len({
        ((row.get("fund_house") or row["scheme_code"]).casefold(), row["folio_number"])
        for row in rows if row["folio_number"]
    })


CLASSIFICATIONS = {"EQUITY": "Equity", "DEBT": "Debt", "HYBRID": "Hybrid", "LIQUID": "Debt"}


def _fund_path(row):
    provider_category, provider_subcategory = category_pair(row.get("scheme_category"))
    classification = row.get("personal_classification")
    personal = row.get("personal_category")
    has_personal_category = bool(personal and personal[0])
    category, subcategory = personal if has_personal_category else (provider_category, provider_subcategory)
    if row.get("personal_category") and not classification and category.casefold() in {"equity", "debt", "hybrid"}:
        classification, category, subcategory = category.title(), subcategory, ""
    if not classification:
        classification = CLASSIFICATIONS.get(row.get("primary_asset_class"), "Needs classification")
    if not has_personal_category and subcategory and category.casefold().removesuffix(" schemes").removesuffix(" scheme") in {"equity", "debt", "hybrid", "other"}:
        category, subcategory = subcategory, ""
    return tuple(label for label in (classification, category, subcategory) if label)


def _categories(rows, total, depth=0):
    groups = defaultdict(list)
    schemes = defaultdict(list)
    for row in rows:
        path = _fund_path(row)
        if depth < len(path):
            groups[path[depth]].append(row)
        else:
            schemes[row["scheme_code"]].append(row)
    result = [
        {"id": f"group:{name}", "name": name, **_fund_stats(group, total),
         "children": _categories(group, total, depth + 1)}
        for name, group in sorted(groups.items())
    ]
    return result + _scheme_rows(schemes, total)


def _scheme_rows(schemes, total):
    return [
        {"id": f"scheme:{code}", "name": group[0].get("scheme_name") or code,
         **_fund_stats(group, total), "units": float(sum(Decimal(str(row["quantity"])) for row in group)),
         "category_missing": not bool(group[0].get("scheme_category") or group[0].get("personal_category")),
         "scheme_code": code,
         "provider_category": list(category_pair(group[0].get("scheme_category"))),
         "personal_category": group[0].get("personal_category"),
         "effective_taxonomy": _fund_path(group[0]),
         "portfolio_names": sorted({name for row in group for name in row.get("portfolio_names", [])})}
        for code, group in sorted(schemes.items())
    ]


def _folio_breakdowns(rows, total):
    groups = defaultdict(list)
    for row in rows:
        if row["folio_number"]:
            house = row.get("fund_house") or row["scheme_code"]
            groups[(house.casefold(), row["folio_number"])].append(row)
    def schemes(group):
        by_scheme = defaultdict(list)
        for row in group:
            by_scheme[row["scheme_code"]].append(row)
        return _scheme_rows(by_scheme, total)

    return [
        {"id": f"{house}:{folio}", "name": folio,
         "fund_house": group[0].get("fund_house") or "Unknown AMC",
         **_fund_stats(group, total), "children": schemes(group)}
        for (house, folio), group in groups.items()
    ]


def _fund_breakdowns(rows):
    total = _value(rows)
    houses = defaultdict(list)
    for row in rows:
        houses[row.get("fund_house", "").casefold()].append(row)
    amc = [
        {"name": group[0].get("fund_house") or "Unknown AMC",
         **_fund_stats(group, total), "folio_count": _folio_count(group)}
        for group in houses.values()
    ]
    return {
        "total": float(total) if total is not None else None,
        "incomplete": total is None,
        "missing_category_count": len({row["scheme_code"] for row in rows if not (row.get("scheme_category") or row.get("personal_category"))}),
        "scheme_count": len({row["scheme_code"] for row in rows}),
        "folio_count": _folio_count(rows),
        "amc": sorted(amc, key=lambda row: (-(row["value"] or 0), row["name"])),
        "categories": _categories(rows, total),
        "folios": _folio_breakdowns(rows, total),
    }


def build_assets_reports(holdings, *, user=None):
    schemes = {row["scheme_code"] for row in holdings if row.get("scheme_code")}
    personal = {
        code: (classification, category, subcategory)
        for code, classification, category, subcategory in PersonalFundCategory.objects.filter(
            user=user, profile__scheme_code__in=schemes
        ).values_list("profile__scheme_code", "classification", "category", "subcategory")
    } if user is not None and schemes else {}
    views = defaultdict(list, {"all": [], "equity": [], "debt": []})
    for row in holdings:
        asset_type = row.get("asset_type", "STOCK")
        if "display_current_value" not in row or asset_type in {"BANK_CASH", "CASH"}:
            continue
        if row.get("scheme_code") in personal:
            classification, category, subcategory = personal[row["scheme_code"]]
            row = {**row, "personal_classification": classification, "personal_category": (category, subcategory)}
        views["all"].append(row)
        views[asset_type].append(row)
        if row.get("overview_class"):
            views[row["overview_class"]].append(row)

    return {
        key: {
            "allocation": {
                "scheme": _allocation(rows),
                **({"folio": _allocation(rows, by_folio=True)} if key == "MUTUAL_FUND" else {}),
                "incomplete": any(row["display_current_value"] is None for row in rows),
            },
            "funds": _fund_breakdowns([row for row in rows if row.get("asset_type") == "MUTUAL_FUND"]),
        }
        for key, rows in views.items()
    }
