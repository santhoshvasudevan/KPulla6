import io
from datetime import date
from decimal import Decimal

import pytest

from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.csv_import import parse_transaction_csv
from transactions.models import Transaction, TransactionType


HEADER = "Action,Date,ASSET SYMBOL,Qty,Price/Share,FEES\n"


def _count_txns():
    return Transaction.objects.count()


def _import(api_client, csv_text, portfolio_id=None):
    url = "/api/v1/transactions/import-csv"
    if portfolio_id is not None:
        url = f"{url}?portfolio_id={portfolio_id}"
    return api_client.post(
        url,
        {"file": io.BytesIO(csv_text.encode("utf-8"))},
        format="multipart",
    )


@pytest.mark.django_db
def test_import_buy_rows(api_client, seeded):
    csv_text = HEADER + "Buy,01/15/24,AAPL,10,150.00,\n"
    response = _import(api_client, csv_text)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["imported_count"] == 1
    assert data["errors"] == []
    txn = Transaction.objects.get(asset_symbol="AAPL")
    assert txn.type == TransactionType.BUY
    assert txn.quantity == Decimal("10")


@pytest.mark.django_db
def test_import_sell_rows(api_client, seeded):
    csv_text = HEADER + "Sell,01/15/24,MSFT,5,100.00,0\n"
    response = _import(api_client, csv_text)
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert Transaction.objects.filter(type=TransactionType.SELL).count() == 1


@pytest.mark.django_db
def test_import_dividend_rows(api_client, seeded):
    csv_text = HEADER + "Dividend,01/15/24,AAPL,10,0,0\n"
    response = _import(api_client, csv_text)
    assert response.status_code == 200
    assert response.json()["success"] is True
    txn = Transaction.objects.get(type=TransactionType.DIVIDEND)
    assert txn.price_per_share == Decimal("0")


@pytest.mark.django_db
def test_import_direct_stock_split_rows(api_client, seeded):
    csv_text = HEADER + "STOCK_SPLIT,01/15/24,AAPL,1,20,0\n"
    response = _import(api_client, csv_text)
    assert response.status_code == 200
    assert response.json()["success"] is True
    txn = Transaction.objects.get(type=TransactionType.STOCK_SPLIT)
    assert txn.split_from == Decimal("1")
    assert txn.split_to == Decimal("20")
    assert txn.currency == "EUR"
    assert txn.quantity == Decimal("0")
    assert txn.price_per_share == Decimal("0")


@pytest.mark.django_db
def test_direct_stock_split_rejects_currency_in_price_share(api_client, seeded):
    csv_text = HEADER + "STOCK_SPLIT,01/15/24,AAPL,1,20 €,0\n"
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any(e["field"] == "split_to" for e in data["errors"])


@pytest.mark.django_db
def test_import_defaults_fees_to_zero(api_client, seeded):
    csv_text = HEADER + "Buy,01/15/24,AAPL,10,150.00,\n"
    _import(api_client, csv_text)
    assert Transaction.objects.get().fees == Decimal("0")


@pytest.mark.django_db
def test_import_defaults_portfolio_to_default(api_client, seeded):
    default = ensure_default_portfolio()
    other = Portfolio.objects.create(name="Other", base_currency="EUR", is_active=True)
    csv_text = HEADER + "Buy,01/15/24,AAPL,10,150.00,0\n"
    _import(api_client, csv_text)
    assert Transaction.objects.get().portfolio_id == default.id
    assert Transaction.objects.get().portfolio_id != other.id


@pytest.mark.django_db
def test_import_assigns_provided_portfolio_id(api_client, seeded):
    other = Portfolio.objects.create(name="Target", base_currency="EUR", is_active=True)
    csv_text = HEADER + "Buy,01/15/24,AAPL,10,150.00,0\n"
    response = _import(api_client, csv_text, portfolio_id=other.id)
    assert response.status_code == 200
    assert Transaction.objects.get().portfolio_id == other.id


@pytest.mark.django_db
def test_import_normalizes_asset_symbols(api_client, seeded):
    csv_text = HEADER + "Buy,01/15/24,aapl,10,150.00,0\n"
    _import(api_client, csv_text)
    assert Transaction.objects.get().asset_symbol == "AAPL"


@pytest.mark.django_db
def test_import_rejects_missing_file(api_client, seeded):
    response = api_client.post("/api/v1/transactions/import-csv", {}, format="multipart")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["imported_count"] == 0
    assert any(e["field"] == "file" for e in data["errors"])


@pytest.mark.django_db
def test_import_rejects_non_utf8(api_client, seeded):
    response = api_client.post(
        "/api/v1/transactions/import-csv",
        {"file": io.BytesIO(b"\xff\xfe")},
        format="multipart",
    )
    data = response.json()
    assert data["success"] is False
    assert any("UTF-8" in e["message"] for e in data["errors"])


@pytest.mark.django_db
def test_import_rejects_missing_columns(api_client, seeded):
    csv_text = "Action,Date\nBuy,01/15/24\n"
    response = _import(api_client, csv_text)
    data = response.json()
    assert data["success"] is False
    assert any(e["field"] == "headers" for e in data["errors"])


@pytest.mark.django_db
def test_import_rejects_invalid_date(api_client, seeded):
    csv_text = HEADER + "Buy,99/99/24,AAPL,10,150.00,0\n"
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any(e["field"] == "Date" for e in data["errors"])


@pytest.mark.django_db
def test_import_rejects_empty_qty_for_buy_sell(api_client, seeded):
    csv_text = HEADER + "Buy,01/15/24,AAPL,,150.00,0\n"
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any(e["field"] == "Qty" for e in data["errors"])


@pytest.mark.django_db
def test_import_rejects_non_numeric_qty(api_client, seeded):
    csv_text = HEADER + "Buy,01/15/24,AAPL,abc,150.00,0\n"
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any(e["field"] == "Qty" for e in data["errors"])


@pytest.mark.django_db
def test_import_rejects_negative_price(api_client, seeded):
    csv_text = HEADER + "Buy,01/15/24,AAPL,10,-5.00,0\n"
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any(e["field"] == "Price/Share" for e in data["errors"])


@pytest.mark.django_db
def test_import_rejects_invalid_action(api_client, seeded):
    csv_text = HEADER + "HOLD,01/15/24,AAPL,10,150.00,0\n"
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any(e["field"] == "Action" for e in data["errors"])


@pytest.mark.django_db
def test_import_rejects_unknown_portfolio_id(api_client, seeded):
    csv_text = HEADER + "Buy,01/15/24,AAPL,10,150.00,0\n"
    response = _import(api_client, csv_text, portfolio_id=999999)
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "success" not in body


@pytest.mark.django_db
def test_import_rejects_inactive_portfolio_id(api_client, seeded):
    inactive = Portfolio.objects.create(name="Inactive", is_active=False)
    csv_text = HEADER + "Buy,01/15/24,AAPL,10,150.00,0\n"
    response = _import(api_client, csv_text, portfolio_id=inactive.id)
    assert response.status_code == 404


@pytest.mark.django_db
def test_import_rejects_invalid_stock_split_split_from(api_client, seeded):
    csv_text = HEADER + "STOCK_SPLIT,01/15/24,AAPL,0,20,0\n"
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any(e["field"] == "split_from" for e in data["errors"])


@pytest.mark.django_db
def test_import_rejects_invalid_stock_split_split_to(api_client, seeded):
    csv_text = HEADER + "STOCK_SPLIT,01/15/24,AAPL,1,0,0\n"
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any(e["field"] == "split_to" for e in data["errors"])


@pytest.mark.django_db
def test_import_returns_row_level_errors(api_client, seeded):
    csv_text = HEADER + "Buy,01/15/24,AAPL,-1,150.00,0\n"
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert data["imported_count"] == 0
    assert len(data["errors"]) >= 1
    err = data["errors"][0]
    assert "row" in err and "field" in err and "message" in err


@pytest.mark.django_db
def test_import_all_or_nothing(api_client, seeded):
    before = _count_txns()
    csv_text = (
        HEADER
        + "Buy,01/15/24,XX,10,100.00,0\n"
        + "Buy,01/15/24,YY,-1,100.00,0\n"
    )
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert data["imported_count"] == 0
    assert _count_txns() == before


@pytest.mark.django_db
def test_swap_two_rows_create_stock_split(api_client, seeded):
    csv_text = (
        HEADER
        + "Swap,12/3/24,ANET,-35,393.70 €,0\n"
        + "Swap,12/3/24,ANET,140,98.42 €,0\n"
    )
    payloads, errs = parse_transaction_csv(csv_text)
    assert not errs
    assert len(payloads) == 1
    assert payloads[0]["type"] == TransactionType.STOCK_SPLIT
    assert payloads[0]["split_from"] == Decimal("1")
    assert payloads[0]["split_to"] == Decimal("4")

    response = _import(api_client, csv_text)
    assert response.json()["success"] is True
    assert response.json()["imported_count"] == 1
    txn = Transaction.objects.get(asset_symbol="ANET")
    assert txn.type == TransactionType.STOCK_SPLIT
    assert txn.split_from == Decimal("1")
    assert txn.split_to == Decimal("4")


@pytest.mark.django_db
def test_swap_incomplete_pair_rejected(api_client, seeded):
    csv_text = HEADER + "Swap,12/3/24,ANET,-35,100.00,0\n"
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any("SWAP requires exactly two" in e["message"] for e in data["errors"])


@pytest.mark.django_db
def test_swap_ambiguous_same_sign_rejected(api_client, seeded):
    csv_text = (
        HEADER
        + "Swap,12/3/24,ANET,35,100.00,0\n"
        + "Swap,12/3/24,ANET,140,98.42,0\n"
    )
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any("one negative and one positive" in e["message"] for e in data["errors"])


@pytest.mark.django_db
def test_parse_mmddyy_date():
    payloads, errs = parse_transaction_csv(HEADER + "buy,01/15/24,MSFT,5,100.00,0\n")
    assert not errs
    assert payloads[0]["date"] == date(2024, 1, 15)


@pytest.mark.django_db
def test_parse_negative_quantity_error():
    _, errs = parse_transaction_csv(HEADER + "Buy,01/15/24,AAPL,-1,150.00,0\n")
    assert errs
    assert any(e["field"] == "Qty" for e in errs)
