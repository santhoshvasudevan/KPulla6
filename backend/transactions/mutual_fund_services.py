from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction as db_transaction

from market_data.models import Asset, AssetType, MutualFundProfile
from market_data.mutual_fund_classification_bridge import maybe_apply_inferred_asset_class
from market_data.nav_lookup import normalize_scheme_code
from transactions.mf_nav_validation import verify_mutual_fund_nav_inputs
from portfolios.services import PortfolioNotFoundError
from portfolios.scope import resolve_portfolio_id_or_default
from transactions.models import (
    Folio,
    MutualFundTransactionDetail,
    Transaction,
    TransactionType,
)
from transactions.cash_settlement import sync_mutual_fund_settlement
from finance.cash import mf_sell_cash_proceeds
from transactions.services import (
    TransactionNotFoundError,
    TransactionValidationError,
    _parse_optional_positive_decimal,
    _validate_sell_cash_fields,
    get_transaction,
)


@dataclass(frozen=True)
class MutualFundValidatedPayload:
    portfolio_id: int | None
    scheme_code: str
    scheme_name: str
    folio_number: str
    txn_type: str
    investment_date: Any
    nav_date: Any
    nav: Decimal
    units_allotted: Decimal
    paid_value: Decimal
    market_value: Decimal
    currency: str
    fees: Decimal
    fund_house: str
    scheme_type: str
    scheme_category: str
    isin_growth: str
    isin_reinvestment: str
    direct_or_regular: str
    growth_or_idcw: str
    actual_cash_received: Decimal | None
    settlement_note: str | None


def _require_decimal(value, *, field: str, gt_zero: bool = False, ge_zero: bool = False) -> Decimal:
    if value is None:
        raise TransactionValidationError(f"{field} is required")
    try:
        dec = Decimal(str(value))
    except Exception as exc:
        raise TransactionValidationError(f"{field} must be a number") from exc
    if gt_zero and dec <= 0:
        raise TransactionValidationError(f"{field} must be greater than 0")
    if ge_zero and dec < 0:
        raise TransactionValidationError(f"{field} must be greater than or equal to 0")
    return dec


def _resolve_fees(
    *,
    fees: Decimal | None,
    paid_value: Decimal,
    market_value: Decimal,
) -> Decimal:
    if fees is not None:
        if fees < 0:
            raise TransactionValidationError("fees must be greater than or equal to 0")
        return fees
    computed = paid_value - market_value
    if computed < 0:
        raise TransactionValidationError(
            "fees cannot be negative; paid_value must be greater than or equal to market_value "
            "when fees is omitted"
        )
    return computed


def _nav_verification_for(payload: MutualFundValidatedPayload) -> tuple[str, str]:
    result = verify_mutual_fund_nav_inputs(
        scheme_code=payload.scheme_code,
        nav_date=payload.nav_date,
        entered_nav=payload.nav,
        units_allotted=payload.units_allotted,
        market_value=payload.market_value,
    )
    return result.status, result.message


def validate_mutual_fund_transaction_payload(data: dict[str, Any]) -> MutualFundValidatedPayload:
    scheme_code = normalize_scheme_code(data.get("scheme_code") or "")
    if not scheme_code:
        raise TransactionValidationError("scheme_code is required")

    scheme_name = (data.get("scheme_name") or "").strip()
    if not scheme_name:
        raise TransactionValidationError("scheme_name is required")

    folio_number = (data.get("folio_number") or "").strip()
    if not folio_number:
        raise TransactionValidationError("folio_number is required")

    txn_type = data.get("type")
    if txn_type not in {TransactionType.BUY, TransactionType.SELL}:
        raise TransactionValidationError("Mutual fund transactions support BUY and SELL only")

    investment_date = data.get("investment_date")
    nav_date = data.get("nav_date")
    if investment_date is None:
        raise TransactionValidationError("investment_date is required")
    if nav_date is None:
        raise TransactionValidationError("nav_date is required")

    nav = _require_decimal(data.get("nav"), field="nav", gt_zero=True)
    units_allotted = _require_decimal(data.get("units_allotted"), field="units_allotted", gt_zero=True)
    paid_value = _require_decimal(data.get("paid_value"), field="paid_value", ge_zero=True)
    market_value = _require_decimal(data.get("market_value"), field="market_value", ge_zero=True)

    fees_raw = data.get("fees")
    fees = None if fees_raw is None else _require_decimal(fees_raw, field="fees", ge_zero=True)
    fees = _resolve_fees(fees=fees, paid_value=paid_value, market_value=market_value)

    currency = (data.get("currency") or "INR").strip().upper() or "INR"

    parsed_actual = _parse_optional_positive_decimal(
        data.get("actual_cash_received"), field="actual_cash_received"
    )
    calculated_proceeds = None
    if txn_type == TransactionType.SELL:
        calculated_proceeds = mf_sell_cash_proceeds(
            paid_value=paid_value,
            units_allotted=units_allotted,
            nav=nav,
            fees=fees,
        )
    validated_actual, validated_note = _validate_sell_cash_fields(
        txn_type=txn_type,
        calculated_proceeds=calculated_proceeds,
        actual_cash_received=parsed_actual,
        settlement_note=data.get("settlement_note"),
    )

    return MutualFundValidatedPayload(
        portfolio_id=data.get("portfolio_id"),
        scheme_code=scheme_code,
        scheme_name=scheme_name,
        folio_number=folio_number,
        txn_type=txn_type,
        investment_date=investment_date,
        nav_date=nav_date,
        nav=nav,
        units_allotted=units_allotted,
        paid_value=paid_value,
        market_value=market_value,
        currency=currency,
        fees=fees,
        fund_house=(data.get("fund_house") or "").strip(),
        scheme_type=(data.get("scheme_type") or "").strip(),
        scheme_category=(data.get("scheme_category") or "").strip(),
        isin_growth=(data.get("isin_growth") or "").strip(),
        isin_reinvestment=(data.get("isin_reinvestment") or "").strip(),
        direct_or_regular=(data.get("direct_or_regular") or "").strip(),
        growth_or_idcw=(data.get("growth_or_idcw") or "").strip(),
        actual_cash_received=validated_actual,
        settlement_note=validated_note,
    )


def _ensure_mf_asset(payload: MutualFundValidatedPayload) -> Asset:
    asset, created = Asset.objects.get_or_create(
        asset_type=AssetType.MUTUAL_FUND,
        symbol=payload.scheme_code,
        defaults={
            "display_name": payload.scheme_name,
            "currency": payload.currency,
            "provider": "amfi",
            "provider_symbol": payload.scheme_code,
            "region": "IN",
            "is_active": True,
        },
    )
    if not created and payload.scheme_name and asset.display_name != payload.scheme_name:
        asset.display_name = payload.scheme_name
        asset.save(update_fields=["display_name", "updated_at"])
    return asset


def _ensure_mf_profile(asset: Asset, payload: MutualFundValidatedPayload) -> MutualFundProfile:
    profile, created = MutualFundProfile.objects.get_or_create(
        asset=asset,
        defaults={
            "scheme_code": payload.scheme_code,
            "scheme_name": payload.scheme_name,
            "fund_house": payload.fund_house,
            "scheme_type": payload.scheme_type,
            "scheme_category": payload.scheme_category,
            "isin_growth": payload.isin_growth,
            "isin_reinvestment": payload.isin_reinvestment,
            "direct_or_regular": payload.direct_or_regular,
            "growth_or_idcw": payload.growth_or_idcw,
        },
    )
    if not created:
        update_fields: list[str] = []
        if payload.scheme_name and profile.scheme_name != payload.scheme_name:
            profile.scheme_name = payload.scheme_name
            update_fields.append("scheme_name")
        for field, value in (
            ("fund_house", payload.fund_house),
            ("scheme_type", payload.scheme_type),
            ("scheme_category", payload.scheme_category),
            ("isin_growth", payload.isin_growth),
            ("isin_reinvestment", payload.isin_reinvestment),
            ("direct_or_regular", payload.direct_or_regular),
            ("growth_or_idcw", payload.growth_or_idcw),
        ):
            if value and getattr(profile, field) != value:
                setattr(profile, field, value)
                update_fields.append(field)
        if update_fields:
            update_fields.append("updated_at")
            profile.save(update_fields=update_fields)
    return profile


def _ensure_folio(*, portfolio_id: int, asset: Asset, folio_number: str) -> Folio:
    folio, _ = Folio.objects.get_or_create(
        portfolio_id=portfolio_id,
        asset=asset,
        folio_number=folio_number,
        defaults={"is_active": True},
    )
    return folio


@db_transaction.atomic
def create_mutual_fund_transaction(
    user: AbstractBaseUser, *, validated_data: dict[str, Any]
) -> Transaction:
    payload = validate_mutual_fund_transaction_payload(validated_data)
    try:
        portfolio_id = resolve_portfolio_id_or_default(user, payload.portfolio_id)
    except PortfolioNotFoundError:
        raise

    asset = _ensure_mf_asset(payload)
    profile = _ensure_mf_profile(asset, payload)
    maybe_apply_inferred_asset_class(asset, profile)
    folio = _ensure_folio(
        portfolio_id=portfolio_id,
        asset=asset,
        folio_number=payload.folio_number,
    )

    nav_status, nav_message = _nav_verification_for(payload)

    txn = Transaction.objects.create(
        portfolio_id=portfolio_id,
        asset_symbol=payload.scheme_code,
        date=payload.nav_date,
        type=payload.txn_type,
        quantity=payload.units_allotted,
        price_per_share=payload.nav,
        currency=payload.currency,
        fees=payload.fees,
        actual_cash_received=payload.actual_cash_received,
        settlement_note=payload.settlement_note,
    )
    detail = MutualFundTransactionDetail.objects.create(
        transaction=txn,
        folio=folio,
        investment_date=payload.investment_date,
        nav_date=payload.nav_date,
        nav=payload.nav,
        units_allotted=payload.units_allotted,
        paid_value=payload.paid_value,
        market_value=payload.market_value,
        nav_verification_status=nav_status,
        nav_verification_message=nav_message,
    )
    sync_mutual_fund_settlement(txn, detail)
    return get_transaction(user, txn.id)


@db_transaction.atomic
def update_mutual_fund_transaction(
    user: AbstractBaseUser,
    transaction_id: int,
    *,
    validated_data: dict[str, Any],
    update_portfolio: bool,
) -> Transaction:
    transaction = get_transaction(user, transaction_id)
    try:
        transaction.mutual_fund_detail
    except MutualFundTransactionDetail.DoesNotExist as exc:
        raise TransactionValidationError("Transaction is not a mutual fund transaction") from exc

    payload = validate_mutual_fund_transaction_payload(validated_data)

    if update_portfolio:
        try:
            portfolio_id = resolve_portfolio_id_or_default(user, payload.portfolio_id)
        except PortfolioNotFoundError:
            raise
    else:
        portfolio_id = transaction.portfolio_id

    asset = _ensure_mf_asset(payload)
    profile = _ensure_mf_profile(asset, payload)
    maybe_apply_inferred_asset_class(asset, profile)
    folio = _ensure_folio(
        portfolio_id=portfolio_id,
        asset=asset,
        folio_number=payload.folio_number,
    )

    nav_status, nav_message = _nav_verification_for(payload)

    transaction.portfolio_id = portfolio_id
    transaction.asset_symbol = payload.scheme_code
    transaction.date = payload.nav_date
    transaction.type = payload.txn_type
    transaction.quantity = payload.units_allotted
    transaction.price_per_share = payload.nav
    transaction.currency = payload.currency
    transaction.fees = payload.fees
    transaction.actual_cash_received = payload.actual_cash_received
    transaction.settlement_note = payload.settlement_note
    transaction.save()

    detail = transaction.mutual_fund_detail
    detail.folio = folio
    detail.investment_date = payload.investment_date
    detail.nav_date = payload.nav_date
    detail.nav = payload.nav
    detail.units_allotted = payload.units_allotted
    detail.paid_value = payload.paid_value
    detail.market_value = payload.market_value
    detail.nav_verification_status = nav_status
    detail.nav_verification_message = nav_message
    detail.save()

    sync_mutual_fund_settlement(transaction, detail)
    return get_transaction(user, transaction.id)
