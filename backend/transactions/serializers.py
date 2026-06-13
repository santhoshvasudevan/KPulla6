from decimal import Decimal

from rest_framework import serializers

from transactions.models import Transaction, TransactionType
from transactions.mutual_fund_services import validate_mutual_fund_transaction_payload
from transactions.services import validate_transaction_payload


class TransactionSerializer(serializers.ModelSerializer):
    portfolio_id = serializers.IntegerField(source="portfolio.id", read_only=True)
    portfolio_name = serializers.CharField(source="portfolio.name", read_only=True)

    class Meta:
        model = Transaction
        fields = (
            "id",
            "asset_symbol",
            "date",
            "type",
            "quantity",
            "price_per_share",
            "portfolio_id",
            "currency",
            "fees",
            "actual_cash_received",
            "settlement_note",
            "split_from",
            "split_to",
            "portfolio_name",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for key in (
            "quantity",
            "price_per_share",
            "fees",
            "actual_cash_received",
            "split_from",
            "split_to",
        ):
            if data.get(key) is not None:
                data[key] = float(data[key])

        detail = getattr(instance, "mutual_fund_detail", None)
        if detail is not None:
            profile = getattr(detail.folio.asset, "mutual_fund_profile", None)
            data["asset_type"] = "MUTUAL_FUND"
            data["scheme_code"] = instance.asset_symbol
            data["scheme_name"] = profile.scheme_name if profile else detail.folio.asset.display_name
            data["folio_number"] = detail.folio.folio_number
            data["investment_date"] = detail.investment_date.isoformat()
            data["nav_date"] = detail.nav_date.isoformat()
            data["nav"] = float(detail.nav)
            data["units_allotted"] = float(detail.units_allotted)
            data["paid_value"] = float(detail.paid_value)
            data["market_value"] = float(detail.market_value)
            data["nav_verification_status"] = detail.nav_verification_status
            if detail.nav_verification_message:
                data["nav_verification_message"] = detail.nav_verification_message
        return data


class TransactionWriteSerializer(serializers.Serializer):
    asset_symbol = serializers.CharField(max_length=32)
    date = serializers.DateField()
    type = serializers.ChoiceField(choices=TransactionType.choices)
    quantity = serializers.DecimalField(
        max_digits=18,
        decimal_places=8,
        required=False,
        allow_null=True,
    )
    price_per_share = serializers.DecimalField(
        max_digits=18,
        decimal_places=6,
        required=False,
        allow_null=True,
    )
    portfolio_id = serializers.IntegerField(required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, required=False, allow_null=True)
    fees = serializers.DecimalField(
        max_digits=18,
        decimal_places=4,
        required=False,
        allow_null=True,
    )
    split_from = serializers.DecimalField(
        max_digits=18,
        decimal_places=8,
        required=False,
        allow_null=True,
    )
    split_to = serializers.DecimalField(
        max_digits=18,
        decimal_places=8,
        required=False,
        allow_null=True,
    )
    actual_cash_received = serializers.DecimalField(
        max_digits=18,
        decimal_places=4,
        required=False,
        allow_null=True,
    )
    settlement_note = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    def validate(self, attrs):
        try:
            validated = validate_transaction_payload(
                txn_type=attrs["type"],
                asset_symbol=attrs.get("asset_symbol"),
                date=attrs.get("date"),
                quantity=attrs.get("quantity"),
                price_per_share=attrs.get("price_per_share"),
                fees=attrs.get("fees"),
                currency=attrs.get("currency"),
                split_from=attrs.get("split_from"),
                split_to=attrs.get("split_to"),
                actual_cash_received=attrs.get("actual_cash_received"),
                settlement_note=attrs.get("settlement_note"),
            )
        except Exception as exc:
            from transactions.services import TransactionValidationError

            if isinstance(exc, TransactionValidationError):
                raise serializers.ValidationError(str(exc))
            raise
        attrs.update(validated)
        return attrs


class MutualFundTransactionWriteSerializer(serializers.Serializer):
    asset_type = serializers.ChoiceField(choices=[("MUTUAL_FUND", "Mutual fund")])
    scheme_code = serializers.CharField(max_length=32)
    scheme_name = serializers.CharField(max_length=512)
    folio_number = serializers.CharField(max_length=64)
    type = serializers.ChoiceField(choices=[TransactionType.BUY, TransactionType.SELL])
    investment_date = serializers.DateField()
    nav_date = serializers.DateField()
    nav = serializers.DecimalField(max_digits=18, decimal_places=6)
    units_allotted = serializers.DecimalField(max_digits=18, decimal_places=8)
    paid_value = serializers.DecimalField(max_digits=18, decimal_places=4)
    market_value = serializers.DecimalField(max_digits=18, decimal_places=4)
    portfolio_id = serializers.IntegerField(required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, required=False, allow_null=True)
    fees = serializers.DecimalField(
        max_digits=18,
        decimal_places=4,
        required=False,
        allow_null=True,
    )
    actual_cash_received = serializers.DecimalField(
        max_digits=18,
        decimal_places=4,
        required=False,
        allow_null=True,
    )
    settlement_note = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    fund_house = serializers.CharField(max_length=255, required=False, allow_blank=True)
    scheme_type = serializers.CharField(max_length=128, required=False, allow_blank=True)
    scheme_category = serializers.CharField(max_length=255, required=False, allow_blank=True)
    isin_growth = serializers.CharField(max_length=12, required=False, allow_blank=True)
    isin_reinvestment = serializers.CharField(max_length=12, required=False, allow_blank=True)
    direct_or_regular = serializers.CharField(max_length=16, required=False, allow_blank=True)
    growth_or_idcw = serializers.CharField(max_length=16, required=False, allow_blank=True)

    def validate(self, attrs):
        from transactions.services import TransactionValidationError

        data = dict(attrs)
        if hasattr(self, "initial_data") and "portfolio_id" in self.initial_data:
            data["portfolio_id"] = self.initial_data.get("portfolio_id")

        try:
            validated = validate_mutual_fund_transaction_payload(data)
        except TransactionValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return {
            "portfolio_id": validated.portfolio_id,
            "scheme_code": validated.scheme_code,
            "scheme_name": validated.scheme_name,
            "folio_number": validated.folio_number,
            "type": validated.txn_type,
            "investment_date": validated.investment_date,
            "nav_date": validated.nav_date,
            "nav": validated.nav,
            "units_allotted": validated.units_allotted,
            "paid_value": validated.paid_value,
            "market_value": validated.market_value,
            "currency": validated.currency,
            "fees": validated.fees,
            "actual_cash_received": validated.actual_cash_received,
            "settlement_note": validated.settlement_note,
            "fund_house": validated.fund_house,
            "scheme_type": validated.scheme_type,
            "scheme_category": validated.scheme_category,
            "isin_growth": validated.isin_growth,
            "isin_reinvestment": validated.isin_reinvestment,
            "direct_or_regular": validated.direct_or_regular,
            "growth_or_idcw": validated.growth_or_idcw,
        }


class TransactionListSerializer(serializers.Serializer):
    items = TransactionSerializer(many=True)
    total = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    pages = serializers.IntegerField()


class CsvImportErrorSerializer(serializers.Serializer):
    row = serializers.IntegerField()
    field = serializers.CharField()
    message = serializers.CharField()


class CsvImportResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    imported_count = serializers.IntegerField()
    errors = CsvImportErrorSerializer(many=True)


class CsvCashShortfallSerializer(serializers.Serializer):
    portfolio_id = serializers.IntegerField()
    portfolio_name = serializers.CharField()
    date = serializers.DateField()
    currency = serializers.CharField()
    required = serializers.FloatField()
    available_before = serializers.FloatField()
    shortfall = serializers.FloatField()
    reason = serializers.CharField()


class CsvProposedDepositSerializer(serializers.Serializer):
    portfolio_id = serializers.IntegerField()
    portfolio_name = serializers.CharField(required=False, allow_blank=True)
    date = serializers.DateField()
    currency = serializers.CharField()
    amount = serializers.FloatField()
    source_of_funds = serializers.CharField()
    note = serializers.CharField()


class CsvCashPreviewSummarySerializer(serializers.Serializer):
    rows = serializers.IntegerField()
    cash_aware_rows = serializers.IntegerField()
    proposed_deposit_count = serializers.IntegerField()
    total_shortfall_by_currency = serializers.ListField(child=serializers.DictField())


class CsvCashPreviewResponseSerializer(serializers.Serializer):
    cash_aware = serializers.BooleanField()
    can_import_without_deposits = serializers.BooleanField()
    shortfalls = CsvCashShortfallSerializer(many=True)
    proposed_deposits = CsvProposedDepositSerializer(many=True)
    row_errors = CsvImportErrorSerializer(many=True)
    summary = CsvCashPreviewSummarySerializer()
