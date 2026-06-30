from decimal import Decimal

from rest_framework import serializers

from cash.ledger_details import build_ledger_entry_details
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


class CashBulkEntriesRequestSerializer(serializers.Serializer):
    portfolio_id = serializers.IntegerField()
    entry_type = serializers.CharField()
    currency = serializers.CharField(max_length=3)
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    frequency = serializers.CharField()
    source_of_funds = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_amount(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("amount must be positive")
        return value


class CashBulkEntriesApplyRequestSerializer(CashBulkEntriesRequestSerializer):
    confirmed = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if attrs.get("confirmed") is not True:
            raise serializers.ValidationError(
                "Bulk cash apply requires explicit confirmation."
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


class CashTransferWriteSerializer(serializers.Serializer):
    source_portfolio_id = serializers.IntegerField()
    target_portfolio_id = serializers.IntegerField()
    date = serializers.DateField()
    note = serializers.CharField(required=False, allow_blank=True, default="")
    # Legacy same-currency (Cash-8A)
    currency = serializers.CharField(max_length=3, required=False, allow_null=True)
    amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, allow_null=True
    )
    # Explicit cross-currency (Cash-8B)
    source_currency = serializers.CharField(
        max_length=3, required=False, allow_null=True
    )
    source_amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, allow_null=True
    )
    target_currency = serializers.CharField(
        max_length=3, required=False, allow_null=True
    )
    target_amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, allow_null=True
    )

    def validate_amount(self, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise serializers.ValidationError("amount must be positive")
        return value

    def validate_source_amount(self, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise serializers.ValidationError("source_amount must be positive")
        return value

    def validate_target_amount(self, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise serializers.ValidationError("target_amount must be positive")
        return value

    def validate(self, attrs):
        from cash.services import CashValidationError, parse_transfer_amounts

        try:
            src_ccy, src_amt, tgt_ccy, tgt_amt = parse_transfer_amounts(
                currency=attrs.get("currency"),
                amount=attrs.get("amount"),
                source_currency=attrs.get("source_currency"),
                source_amount=attrs.get("source_amount"),
                target_currency=attrs.get("target_currency"),
                target_amount=attrs.get("target_amount"),
            )
        except CashValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        attrs["source_currency"] = src_ccy
        attrs["source_amount"] = src_amt
        attrs["target_currency"] = tgt_ccy
        attrs["target_amount"] = tgt_amt
        return attrs


def _decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


class CashLedgerReversalWriteSerializer(serializers.Serializer):
    reversal_date = serializers.DateField(required=False, allow_null=True)
    reason = serializers.CharField()

    def validate_reason(self, value: str) -> str:
        if not (value or "").strip():
            raise serializers.ValidationError("reason is required for audit.")
        return value.strip()


class CashLedgerEntrySerializer(serializers.ModelSerializer):
    portfolio_id = serializers.IntegerField(source="portfolio.id", read_only=True)
    portfolio_name = serializers.CharField(source="portfolio.name", read_only=True)
    details = serializers.SerializerMethodField()
    is_reversed = serializers.SerializerMethodField()
    reversed_by_id = serializers.SerializerMethodField()
    is_reversible = serializers.SerializerMethodField()

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
            "details",
            "is_reversal",
            "reverses_id",
            "reversal_reason",
            "is_reversed",
            "reversed_by_id",
            "is_reversible",
            "created_at",
            "updated_at",
        )

    def get_details(self, obj: CashLedgerEntry) -> str:
        return build_ledger_entry_details(obj)

    def get_is_reversed(self, obj: CashLedgerEntry) -> bool:
        from cash.services import ledger_entry_has_been_reversed

        return ledger_entry_has_been_reversed(obj)

    def get_reversed_by_id(self, obj: CashLedgerEntry):
        if obj.is_reversal:
            return None
        row = obj.reversal_rows.filter(is_reversal=True).order_by("id").first()
        return row.id if row else None

    def get_is_reversible(self, obj: CashLedgerEntry) -> bool:
        from cash.reversal_services import is_reversible_manual_entry

        return is_reversible_manual_entry(obj)

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
        if not data.get("reversal_reason"):
            data["reversal_reason"] = None
        return data
