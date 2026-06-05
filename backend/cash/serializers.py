from decimal import Decimal

from rest_framework import serializers

from cash.models import CashLedgerEntry


class CashDepositWriteSerializer(serializers.Serializer):
    portfolio_id = serializers.IntegerField()
    date = serializers.DateField()
    currency = serializers.CharField(max_length=3)
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    source_of_funds = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_amount(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("amount must be positive")
        return value


class CashManualLedgerUpdateSerializer(serializers.Serializer):
    """PUT /cash/ledger/{id} — manual deposit/withdrawal only; portfolio unchanged."""

    date = serializers.DateField()
    currency = serializers.CharField(max_length=3)
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    source_of_funds = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_amount(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("amount must be positive")
        return value


class CashBackfillPreviewRequestSerializer(serializers.Serializer):
    portfolio_id = serializers.IntegerField()
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    mode = serializers.CharField(required=False, default="shortfall")


class CashBackfillApplyRequestSerializer(serializers.Serializer):
    portfolio_id = serializers.IntegerField()
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    mode = serializers.CharField(required=False, default="shortfall")
    confirmed = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if attrs.get("confirmed") is not True:
            raise serializers.ValidationError(
                "Backfill apply requires explicit confirmation."
            )
        return attrs


class CashWithdrawalWriteSerializer(serializers.Serializer):
    portfolio_id = serializers.IntegerField()
    date = serializers.DateField()
    currency = serializers.CharField(max_length=3)
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    source_of_funds = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_amount(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("amount must be positive")
        return value


def _decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


class CashLedgerEntrySerializer(serializers.ModelSerializer):
    portfolio_id = serializers.IntegerField(source="portfolio.id", read_only=True)
    portfolio_name = serializers.CharField(source="portfolio.name", read_only=True)

    class Meta:
        model = CashLedgerEntry
        fields = (
            "id",
            "portfolio_id",
            "portfolio_name",
            "date",
            "currency",
            "entry_type",
            "amount",
            "source_of_funds",
            "linked_transaction_id",
            "transfer_group_id",
            "note",
            "created_at",
            "updated_at",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["date"] = instance.date.isoformat()
        data["amount"] = _decimal_to_float(instance.amount)
        data["created_at"] = instance.created_at.isoformat()
        data["updated_at"] = instance.updated_at.isoformat()
        if not data.get("source_of_funds"):
            data["source_of_funds"] = None
        if not data.get("note"):
            data["note"] = None
        return data
