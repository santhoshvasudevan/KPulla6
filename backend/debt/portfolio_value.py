from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import QuerySet

from debt.bank_account_portfolio import bank_account_associated_portfolio_ids
from debt.bank_ledger_services import bank_account_has_ledger
from debt.models import BankAccount, CashMovement, FixedDeposit, VALUE_CONTRIBUTING_STATUSES
from finance.bank_cash import BankCashMovementPoint, bank_cash_balance
from finance.fixed_deposits import fixed_deposit_principal_value
from fx.lookup import convert_amount_with_fill_from_maps, load_fx_rate_maps
from portfolios import dates as portfolio_dates
from portfolios.scope import ResolvedPortfolioScope

FD_BANK_FX_VALUE_HISTORY_WARNING = (
    "FX rates are missing for some fixed deposit or bank cash value history points."
)


def bank_account_includable_in_scope(
    account: BankAccount,
    scope: ResolvedPortfolioScope,
) -> bool:
    """
    FD-ACC-7 inclusion rules.

    ``all`` scope: each eligible account once.
    Single portfolio: only when associations resolve to that portfolio alone.
    """
    if not account.include_in_portfolio_value or not account.is_active:
        return False
    if not bank_account_has_ledger(account):
        return False

    if scope.kind == "all_active":
        return True

    target = scope.portfolio_ids[0]
    associated = bank_account_associated_portfolio_ids(account.id)
    if not associated:
        return False
    return associated == {target}


@dataclass(frozen=True)
class BankCashHoldingsCalc:
    total_invested: Decimal
    current_value: Decimal
    realized_pl: Decimal
    unrealized_pl: Decimal
    total_pl: Decimal
    any_fx_missing: bool
    warnings: list[str]


def calculate_bank_cash_for_scope(
    user,
    scope: ResolvedPortfolioScope,
    *,
    display_currency: str,
    as_of_date: date | None = None,
) -> BankCashHoldingsCalc:
    """Aggregate ledger-derived bank cash for included accounts in scope."""
    as_of = as_of_date or portfolio_dates.current_date()
    disp_ccy = (display_currency or "EUR").strip().upper() or "EUR"

    accounts = list(
        BankAccount.objects.filter(
            user=user,
            is_active=True,
            include_in_portfolio_value=True,
        ).order_by("name", "id")
    )
    eligible = [a for a in accounts if bank_account_includable_in_scope(a, scope)]
    if not eligible:
        return BankCashHoldingsCalc(
            total_invested=Decimal("0"),
            current_value=Decimal("0"),
            realized_pl=Decimal("0"),
            unrealized_pl=Decimal("0"),
            total_pl=Decimal("0"),
            any_fx_missing=False,
            warnings=[],
        )

    fx_pairs: set[tuple[str, str]] = set()
    for account in eligible:
        if account.currency != disp_ccy:
            fx_pairs.add((account.currency, disp_ccy))
    fx_maps = load_fx_rate_maps(fx_pairs, as_of, as_of) if fx_pairs else {}

    total_invested = Decimal("0")
    current_value = Decimal("0")
    any_fx_missing = False
    warnings: list[str] = []

    for account in eligible:
        balance = account.current_balance
        if balance <= 0:
            continue

        if account.currency == disp_ccy:
            converted = balance
        else:
            converted, fx_st = convert_amount_with_fill_from_maps(
                balance, account.currency, disp_ccy, as_of, fx_maps
            )
            if converted is None:
                any_fx_missing = True
                warnings.append(
                    f"FX unavailable for bank account {account.name} "
                    f"({account.currency}→{disp_ccy})"
                )
                continue
            if fx_st == "fx_unavailable":
                any_fx_missing = True

        total_invested += converted
        current_value += converted

    return BankCashHoldingsCalc(
        total_invested=total_invested,
        current_value=current_value,
        realized_pl=Decimal("0"),
        unrealized_pl=Decimal("0"),
        total_pl=Decimal("0"),
        any_fx_missing=any_fx_missing,
        warnings=warnings,
    )


def build_bank_cash_holding_rows(
    user,
    scope: ResolvedPortfolioScope,
    *,
    display_currency: str,
    as_of_date: date | None = None,
) -> list[dict]:
    """Holdings-table rows for included bank accounts with ledger balance."""
    as_of = as_of_date or portfolio_dates.current_date()
    disp_ccy = (display_currency or "EUR").strip().upper() or "EUR"

    accounts = list(
        BankAccount.objects.filter(
            user=user,
            is_active=True,
            include_in_portfolio_value=True,
        ).order_by("name", "id")
    )
    eligible = [a for a in accounts if bank_account_includable_in_scope(a, scope)]

    fx_pairs: set[tuple[str, str]] = set()
    for account in eligible:
        if account.currency != disp_ccy:
            fx_pairs.add((account.currency, disp_ccy))
    fx_maps = load_fx_rate_maps(fx_pairs, as_of, as_of) if fx_pairs else {}

    rows: list[dict] = []
    for account in eligible:
        balance = account.current_balance
        fx_missing = False
        display_value = balance
        if balance > 0 and account.currency != disp_ccy:
            converted, fx_st = convert_amount_with_fill_from_maps(
                balance, account.currency, disp_ccy, as_of, fx_maps
            )
            if converted is None or fx_st == "fx_unavailable":
                fx_missing = True
                display_value = Decimal("0")
            else:
                display_value = converted

        rows.append(
            {
                "asset_type": "BANK_CASH",
                "asset_symbol": account.name,
                "holding_key": f"bank:{account.id}",
                "bank_account_id": account.id,
                "bank_account_name": account.name,
                "institution_name": account.institution_name,
                "account_number": account.account_number,
                "current_value": float(display_value),
                "invested_amount": float(display_value),
                "invested": float(display_value),
                "realized_pl": 0.0,
                "unrealized_pl": 0.0,
                "realized_gain_loss": 0.0,
                "unrealized_gain_loss": 0.0,
                "currency": account.currency,
                "display_currency": disp_ccy,
                "holding_status": "ok" if balance > 0 else "closed",
                "value_status": "ledger_balance" if balance > 0 else "excluded",
                "fx_status": "fx_unavailable" if fx_missing else "ok",
                "warnings": [],
                "_fx_missing": fx_missing,
            }
        )
    return rows


@dataclass(frozen=True)
class FixedDepositHoldingsCalc:
    total_invested: Decimal
    current_value: Decimal
    realized_pl: Decimal
    unrealized_pl: Decimal
    total_pl: Decimal
    any_fx_missing: bool
    warnings: list[str]


def _value_contributing_fds(scope: ResolvedPortfolioScope) -> QuerySet[FixedDeposit]:
    return (
        FixedDeposit.objects.filter(
            portfolio_id__in=scope.portfolio_ids,
            is_active=True,
            status__in=VALUE_CONTRIBUTING_STATUSES,
        )
        .select_related("portfolio", "bank_account")
    )


def scope_has_contributing_fixed_deposits(scope: ResolvedPortfolioScope) -> bool:
    """True when at least one FD contributes principal to portfolio value."""
    return _value_contributing_fds(scope).exists()


def calculate_fd_holdings_for_scope(
    scope: ResolvedPortfolioScope,
    *,
    display_currency: str,
    as_of_date: date | None = None,
) -> FixedDepositHoldingsCalc:
    """Aggregate FD principal-only values for portfolio summary."""
    as_of = as_of_date or portfolio_dates.current_date()
    disp_ccy = (display_currency or "EUR").strip().upper() or "EUR"

    fds = list(_value_contributing_fds(scope))
    total_invested = Decimal("0")
    current_value = Decimal("0")
    any_fx_missing = False
    warnings: list[str] = []

    fx_pairs: set[tuple[str, str]] = set()
    for fd in fds:
        principal = fixed_deposit_principal_value(fd, as_of)
        if principal <= 0:
            continue
        if fd.currency != disp_ccy:
            fx_pairs.add((fd.currency, disp_ccy))

    today = as_of
    fx_start = today
    fx_maps = load_fx_rate_maps(fx_pairs, fx_start, today) if fx_pairs else {}

    for fd in fds:
        principal = fixed_deposit_principal_value(fd, as_of)
        if principal <= 0:
            continue

        if fd.currency == disp_ccy:
            converted = principal
        else:
            converted, fx_st = convert_amount_with_fill_from_maps(
                principal, fd.currency, disp_ccy, today, fx_maps
            )
            if converted is None:
                any_fx_missing = True
                warnings.append(
                    f"FX unavailable for fixed deposit {fd.institution_name} "
                    f"({fd.currency}→{disp_ccy})"
                )
                continue
            if fx_st == "fx_unavailable":
                any_fx_missing = True

        total_invested += converted
        current_value += converted

    # MVP: principal-only → unrealized P/L is zero
    return FixedDepositHoldingsCalc(
        total_invested=total_invested,
        current_value=current_value,
        realized_pl=Decimal("0"),
        unrealized_pl=Decimal("0"),
        total_pl=Decimal("0"),
        any_fx_missing=any_fx_missing,
        warnings=warnings,
    )


def calculate_fd_bank_terminal_for_scope(
    user,
    scope: ResolvedPortfolioScope,
    *,
    display_currency: str,
    as_of_date: date | None = None,
) -> tuple[Decimal, bool, list[str]]:
    """FD principal + included bank cash for XIRR terminal / wealth-pool alignment."""
    if user is None:
        return Decimal("0"), False, []
    as_of = as_of_date or portfolio_dates.current_date()
    disp_ccy = (display_currency or "EUR").strip().upper() or "EUR"
    fd = calculate_fd_holdings_for_scope(scope, display_currency=disp_ccy, as_of_date=as_of)
    bank = calculate_bank_cash_for_scope(
        user, scope, display_currency=disp_ccy, as_of_date=as_of
    )
    total = fd.current_value + bank.current_value
    fx_missing = fd.any_fx_missing or bank.any_fx_missing
    warnings = list(fd.warnings) + list(bank.warnings)
    return total, fx_missing, warnings


def build_fd_holding_rows(
    scope: ResolvedPortfolioScope,
    *,
    display_currency: str,
    as_of_date: date | None = None,
) -> list[dict]:
    """Build holdings-table rows for fixed deposits (includes inactive for visibility)."""
    as_of = as_of_date or portfolio_dates.current_date()
    disp_ccy = (display_currency or "EUR").strip().upper() or "EUR"

    fds = list(
        FixedDeposit.objects.filter(portfolio_id__in=scope.portfolio_ids, is_active=True)
        .select_related("portfolio", "bank_account")
        .order_by("institution_name", "deposit_account_number", "id")
    )

    fx_pairs: set[tuple[str, str]] = set()
    for fd in fds:
        if fd.currency != disp_ccy:
            fx_pairs.add((fd.currency, disp_ccy))
    today = as_of
    fx_maps = load_fx_rate_maps(fx_pairs, today, today) if fx_pairs else {}

    rows: list[dict] = []
    for fd in fds:
        principal = fixed_deposit_principal_value(fd, as_of)
        fx_missing = False
        display_value = principal
        if principal > 0 and fd.currency != disp_ccy:
            converted, fx_st = convert_amount_with_fill_from_maps(
                principal, fd.currency, disp_ccy, today, fx_maps
            )
            if converted is None or fx_st == "fx_unavailable":
                fx_missing = True
                display_value = Decimal("0")
            else:
                display_value = converted

        value_status = "principal_only"
        if fd.status in ("CLOSED", "MATURED_SETTLED", "CANCELLED") or not fd.is_active:
            value_status = "closed"
        elif principal <= 0:
            value_status = "excluded"

        rows.append(
            {
                "asset_type": "FIXED_DEPOSIT",
                "asset_symbol": f"FD {fd.institution_name}",
                "holding_key": f"fd:{fd.id}",
                "fixed_deposit_id": fd.id,
                "portfolio_id": fd.portfolio_id,
                "portfolio_name": fd.portfolio.name,
                "institution_name": fd.institution_name,
                "deposit_account_number": fd.deposit_account_number,
                "bank_account_id": fd.bank_account_id,
                "bank_account_name": fd.bank_account.name,
                "principal_amount": float(fd.principal_amount),
                "current_value": float(display_value),
                "invested_amount": float(fd.principal_amount),
                "invested": float(fd.principal_amount),
                "realized_pl": 0.0,
                "unrealized_pl": 0.0,
                "realized_gain_loss": 0.0,
                "unrealized_gain_loss": 0.0,
                "currency": fd.currency,
                "display_currency": disp_ccy,
                "interest_rate_percent": float(fd.interest_rate_percent),
                "interest_payout_frequency": fd.interest_payout_frequency,
                "investment_date": fd.investment_date.isoformat(),
                "maturity_date": fd.maturity_date.isoformat(),
                "nominee_name": fd.nominee_name or None,
                "status": fd.status,
                "value_status": value_status,
                "holding_status": (
                    "closed"
                    if fd.status in ("CLOSED", "MATURED_SETTLED", "CANCELLED")
                    else "ok"
                ),
                "fx_status": "fx_unavailable" if fx_missing else "ok",
                "warnings": [],
                "_fx_missing": fx_missing,
            }
        )
    return rows


def _classify_asset_class_bucket(primary_asset_class: str | None) -> str:
    pac = (primary_asset_class or "").strip().upper()
    if pac in {"EQUITY"}:
        return "Equity"
    if pac in {"DEBT", "LIQUID"}:
        return "Debt"
    return "Other"


@dataclass(frozen=True)
class AllocationBuckets:
    equity: Decimal
    debt: Decimal
    cash: Decimal
    other: Decimal
    currency: str
    fx_status: str


def calculate_allocation_buckets(
    scope: ResolvedPortfolioScope,
    *,
    display_currency: str,
    stock_mf_holdings: list[dict],
    cash_display_total: Decimal,
) -> AllocationBuckets:
    """
    Backend-driven allocation buckets for dashboard chart.

    Equity: stocks/ETFs + equity MFs (via primary_asset_class).
    Debt: FD principal + debt/liquid MFs.
    Cash / Bank Cash: opt-in ledger bank balances (FD-ACC-7).
    Other: hybrid/commodity/unknown/portfolio broker cash.
    """
    disp_ccy = (display_currency or "EUR").strip().upper() or "EUR"
    equity = Decimal("0")
    debt = Decimal("0")
    cash = Decimal("0")
    other = Decimal("0")
    any_fx_missing = False

    for item in stock_mf_holdings:
        asset_type = item.get("asset_type")
        if asset_type in {"FIXED_DEPOSIT", "BANK_CASH"}:
            if asset_type == "BANK_CASH":
                cv = Decimal(str(item.get("current_value") or 0))
                if cv > 0 and item.get("holding_status") != "closed":
                    cash += cv
                if item.get("fx_status") == "fx_unavailable":
                    any_fx_missing = True
            continue
        cv = Decimal(str(item.get("current_value") or 0))
        if cv <= 0:
            continue
        if item.get("holding_status") == "closed":
            continue
        if asset_type == "MUTUAL_FUND":
            bucket = _classify_asset_class_bucket(item.get("primary_asset_class"))
        else:
            bucket = "Equity"  # stocks/ETFs default to equity
        if bucket == "Equity":
            equity += cv
        elif bucket == "Debt":
            debt += cv
        else:
            other += cv
        if item.get("fx_status") == "fx_unavailable":
            any_fx_missing = True

    fd_calc = calculate_fd_holdings_for_scope(scope, display_currency=disp_ccy)
    debt += fd_calc.current_value
    if fd_calc.any_fx_missing:
        any_fx_missing = True

    if cash_display_total > 0:
        other += cash_display_total

    fx_status = "fx_unavailable" if any_fx_missing else "ok"
    return AllocationBuckets(
        equity=equity,
        debt=debt,
        cash=cash,
        other=other,
        currency=disp_ccy,
        fx_status=fx_status,
    )


def allocation_buckets_payload(buckets: AllocationBuckets) -> dict:
    bucket_rows = [
        {"label": "Equity", "value": float(buckets.equity)},
        {"label": "Debt", "value": float(buckets.debt)},
    ]
    if buckets.cash > 0:
        bucket_rows.append({"label": "Cash / Bank Cash", "value": float(buckets.cash)})
    bucket_rows.append({"label": "Other", "value": float(buckets.other)})
    return {
        "currency": buckets.currency,
        "fx_status": buckets.fx_status,
        "buckets": bucket_rows,
    }


def _date_range_inclusive(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _combine_fx_status(statuses: list[str]) -> str:
    if any(s == "fx_unavailable" for s in statuses):
        return "fx_unavailable"
    if any(s == "filled" for s in statuses):
        return "filled"
    return "ok"


def _fd_contributes_principal_on_date(fd: FixedDeposit, as_of: date) -> bool:
    """
    FD principal in value history.

    Inclusive from ``investment_date``; exclusive from ``settlement_date`` when settled.
    """
    if not fd.is_active:
        return False
    if as_of < fd.investment_date:
        return False
    settlement = getattr(fd, "settlement", None)
    if settlement is not None:
        return as_of < settlement.settlement_date
    return fd.status in VALUE_CONTRIBUTING_STATUSES


def _fds_for_value_timeseries(user, scope: ResolvedPortfolioScope) -> list[FixedDeposit]:
    return list(
        FixedDeposit.objects.filter(
            user=user,
            portfolio_id__in=scope.portfolio_ids,
            is_active=True,
        )
        .select_related("settlement")
        .order_by("investment_date", "id")
    )


def value_timeseries_inception_date(
    user,
    scope: ResolvedPortfolioScope,
    *,
    today: date | None = None,
) -> date | None:
    """Earliest FD investment_date or included-bank movement date in scope."""
    _ = today
    candidates: list[date] = []
    fds = _fds_for_value_timeseries(user, scope)
    if fds:
        candidates.append(min(fd.investment_date for fd in fds))
    accounts = list(
        BankAccount.objects.filter(
            user=user,
            is_active=True,
            include_in_portfolio_value=True,
        )
    )
    eligible_ids = [
        a.id
        for a in accounts
        if bank_account_includable_in_scope(a, scope) and bank_account_has_ledger(a)
    ]
    if eligible_ids:
        first_mov = (
            CashMovement.objects.filter(bank_account_id__in=eligible_ids)
            .order_by("movement_date")
            .values_list("movement_date", flat=True)
            .first()
        )
        if first_mov:
            candidates.append(first_mov)
    if not candidates:
        return None
    return min(candidates)


def build_fd_value_timeseries(
    user,
    scope: ResolvedPortfolioScope,
    *,
    display_currency: str,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Daily FD principal totals for portfolio value history (no accrued interest)."""
    disp_ccy = (display_currency or "EUR").strip().upper() or "EUR"
    fds = _fds_for_value_timeseries(user, scope)
    if not fds:
        return []

    fx_pairs: set[tuple[str, str]] = set()
    for fd in fds:
        if fd.currency != disp_ccy:
            fx_pairs.add((fd.currency, disp_ccy))
    fx_maps = load_fx_rate_maps(fx_pairs, start_date, end_date) if fx_pairs else {}

    rows: list[dict] = []
    for as_of in _date_range_inclusive(start_date, end_date):
        total = Decimal("0")
        any_fx_missing = False
        for fd in fds:
            if not _fd_contributes_principal_on_date(fd, as_of):
                continue
            principal = fd.principal_amount
            if fd.currency == disp_ccy:
                total += principal
            else:
                converted, fx_st = convert_amount_with_fill_from_maps(
                    principal, fd.currency, disp_ccy, as_of, fx_maps
                )
                if converted is None or fx_st == "fx_unavailable":
                    any_fx_missing = True
                else:
                    total += converted
        rows.append(
            {
                "date": as_of.isoformat(),
                "fd_value": float(total),
                "fx_status": "fx_unavailable" if any_fx_missing else "ok",
            }
        )
    return rows


def build_bank_cash_value_timeseries(
    user,
    scope: ResolvedPortfolioScope,
    *,
    display_currency: str,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Daily ledger balance totals for opt-in included bank accounts."""
    disp_ccy = (display_currency or "EUR").strip().upper() or "EUR"
    accounts = list(
        BankAccount.objects.filter(
            user=user,
            is_active=True,
            include_in_portfolio_value=True,
        ).order_by("name", "id")
    )
    eligible = [
        a for a in accounts if bank_account_includable_in_scope(a, scope) and bank_account_has_ledger(a)
    ]
    if not eligible:
        return []

    account_ids = [a.id for a in eligible]
    movement_rows = CashMovement.objects.filter(
        bank_account_id__in=account_ids,
        movement_date__lte=end_date,
    ).order_by("bank_account_id", "movement_date", "id")

    points_by_account: dict[int, list[BankCashMovementPoint]] = {
        aid: [] for aid in account_ids
    }
    for row in movement_rows:
        points_by_account[row.bank_account_id].append(
            BankCashMovementPoint(
                movement_date=row.movement_date,
                currency=row.currency,
                amount=row.amount,
                direction=row.direction,
            )
        )

    fx_pairs: set[tuple[str, str]] = set()
    for account in eligible:
        if account.currency != disp_ccy:
            fx_pairs.add((account.currency, disp_ccy))
    fx_maps = load_fx_rate_maps(fx_pairs, start_date, end_date) if fx_pairs else {}

    rows: list[dict] = []
    for as_of in _date_range_inclusive(start_date, end_date):
        total = Decimal("0")
        any_fx_missing = False
        for account in eligible:
            balance = bank_cash_balance(
                points_by_account.get(account.id, []),
                as_of_date=as_of,
            )
            if balance <= 0:
                continue
            if account.currency == disp_ccy:
                total += balance
            else:
                converted, fx_st = convert_amount_with_fill_from_maps(
                    balance, account.currency, disp_ccy, as_of, fx_maps
                )
                if converted is None or fx_st == "fx_unavailable":
                    any_fx_missing = True
                else:
                    total += converted
        rows.append(
            {
                "date": as_of.isoformat(),
                "bank_cash_value": float(total),
                "fx_status": "fx_unavailable" if any_fx_missing else "ok",
            }
        )
    return rows


def merge_fd_bank_into_value_timeseries(
    investment_ts: list[dict],
    *,
    user,
    scope: ResolvedPortfolioScope,
    display_currency: str,
    start_date: date,
    end_date: date,
    include_fd: bool = True,
    include_bank: bool = True,
) -> tuple[list[dict], list[str]]:
    """
    Add daily FD principal and/or included bank cash to ``portfolio_value`` rows.

    Used for value history (FD-ACC-8B) and return metrics (FD-ACC-8C).
    """
    if user is None:
        return investment_ts, []

    fd_ts = (
        build_fd_value_timeseries(
            user,
            scope,
            display_currency=display_currency,
            start_date=start_date,
            end_date=end_date,
        )
        if include_fd
        else []
    )
    bank_ts = (
        build_bank_cash_value_timeseries(
            user,
            scope,
            display_currency=display_currency,
            start_date=start_date,
            end_date=end_date,
        )
        if include_bank
        else []
    )
    warnings: list[str] = []
    if (fd_ts and any(p.get("fx_status") == "fx_unavailable" for p in fd_ts)) or (
        bank_ts and any(p.get("fx_status") == "fx_unavailable" for p in bank_ts)
    ):
        warnings.append(FD_BANK_FX_VALUE_HISTORY_WARNING)

    if not fd_ts and not bank_ts:
        return investment_ts, warnings

    fd_by_date = {p["date"]: p for p in fd_ts}
    bank_by_date = {p["date"]: p for p in bank_ts}

    def _addon_for_date(day: str) -> tuple[float, str]:
        fd_pt = fd_by_date.get(day)
        bank_pt = bank_by_date.get(day)
        addon = float(fd_pt["fd_value"] if fd_pt else 0) + float(
            bank_pt["bank_cash_value"] if bank_pt else 0
        )
        fx_status = _combine_fx_status(
            [
                fd_pt.get("fx_status", "ok") if fd_pt else "ok",
                bank_pt.get("fx_status", "ok") if bank_pt else "ok",
            ]
        )
        return addon, fx_status

    if not investment_ts:
        out: list[dict] = []
        for day in sorted(set(fd_by_date) | set(bank_by_date)):
            if day < start_date.isoformat() or day > end_date.isoformat():
                continue
            addon, fx_status = _addon_for_date(day)
            if addon <= 0:
                continue
            out.append(
                {
                    "date": day,
                    "portfolio_value": addon,
                    "invested_amount": 0.0,
                    "fx_status": fx_status,
                }
            )
        return out, warnings

    out = []
    inv_by_date = {row["date"]: row for row in investment_ts}
    all_dates = sorted(set(inv_by_date) | set(fd_by_date) | set(bank_by_date))
    last_known_inv_pv: float | None = None
    for day in all_dates:
        if day < start_date.isoformat() or day > end_date.isoformat():
            continue
        base_row = inv_by_date.get(day)
        if base_row is not None:
            merged = dict(base_row)
            inv_val = merged.get("portfolio_value")
            if inv_val is not None:
                last_known_inv_pv = float(inv_val)
        elif last_known_inv_pv is not None:
            merged = {
                "date": day,
                "portfolio_value": last_known_inv_pv,
                "invested_amount": 0.0,
                "fx_status": "ok",
            }
        else:
            merged = {
                "date": day,
                "portfolio_value": 0.0,
                "invested_amount": 0.0,
                "fx_status": "ok",
            }
        addon, fx_status = _addon_for_date(day)
        inv_val = merged.get("portfolio_value")
        if inv_val is None:
            merged["portfolio_value"] = None
        else:
            merged["portfolio_value"] = float(inv_val) + addon
        merged["fx_status"] = _combine_fx_status(
            [merged.get("fx_status", "ok"), fx_status]
        )
        if merged.get("portfolio_value") is not None or base_row is not None:
            out.append(merged)
    return out, warnings
