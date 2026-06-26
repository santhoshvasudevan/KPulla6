from decimal import Decimal

from rest_framework import serializers

from debt.models import (
    BankAccount,
    CashMovement,
    CashMovementType,
    FixedDeposit,
    FixedDepositStatus,
    FixedDepositInterestPayment,
    FixedDepositSettlement,
    FixedDepositSettlementType,
    FixedDepositStatus,
    InterestPayoutFrequency,
    MANUAL_API_CASH_MOVEMENT_TYPES,
)
from debt.bank_account_portfolio import (
    bank_account_portfolio_assignment_status,
    fixed_deposit_portfolio_mismatch_warning,
)
from debt.bank_ledger_services import (
    bank_account_ledger_metadata,
    fixed_deposit_has_opening_cash_movement,
    get_fd_opening_cash_movement_id,
    movement_has_been_reversed,
)


class BankAccountSerializer(serializers.ModelSerializer):
    portfolio_id = serializers.IntegerField(
        source="portfolio.id", read_only=True, allow_null=True
    )
    portfolio_name = serializers.CharField(
        source="portfolio.name", read_only=True, allow_null=True
    )
    portfolio_assignment_status = serializers.SerializerMethodField()
    active_fixed_deposit_count = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = (
            "id",
            "name",
            "institution_name",
            "account_number",
            "currency",
            "opening_balance",
            "current_balance",
            "include_in_portfolio_value",
            "portfolio_id",
            "portfolio_name",
            "portfolio_assignment_status",
            "active_fixed_deposit_count",
            "is_active",
            "comment",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "is_active", "created_at", "updated_at")

    def get_portfolio_assignment_status(self, obj: BankAccount) -> str:
        return bank_account_portfolio_assignment_status(obj)

    def get_active_fixed_deposit_count(self, obj: BankAccount) -> int:
        if hasattr(obj, "_active_fixed_deposit_count"):
            return int(obj._active_fixed_deposit_count)
        return FixedDeposit.objects.filter(
            bank_account_id=obj.id,
            is_active=True,
            status=FixedDepositStatus.ACTIVE,
        ).count()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["opening_balance"] = float(instance.opening_balance)
        data["current_balance"] = float(instance.current_balance)
        data["created_at"] = instance.created_at.isoformat()
        data["updated_at"] = instance.updated_at.isoformat()
        if not data.get("comment"):
            data["comment"] = None
        if data.get("portfolio_id") is None:
            data["portfolio_name"] = None
        data.update(bank_account_ledger_metadata(instance))
        return data


class BankAccountCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    institution_name = serializers.CharField(max_length=255)
    account_number = serializers.CharField(max_length=128)
    currency = serializers.CharField(max_length=3)
    opening_balance = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, default=Decimal("0")
    )
    current_balance = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, default=Decimal("0")
    )
    include_in_portfolio_value = serializers.BooleanField(required=False, default=False)
    portfolio_id = serializers.IntegerField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class BankAccountUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    institution_name = serializers.CharField(max_length=255, required=False)
    account_number = serializers.CharField(max_length=128, required=False)
    currency = serializers.CharField(max_length=3, required=False)
    opening_balance = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False
    )
    current_balance = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False
    )
    include_in_portfolio_value = serializers.BooleanField(required=False)
    portfolio_id = serializers.IntegerField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True)


class FixedDepositSerializer(serializers.ModelSerializer):
    portfolio_id = serializers.IntegerField(source="portfolio.id", read_only=True)
    portfolio_name = serializers.CharField(source="portfolio.name", read_only=True)
    bank_account_id = serializers.IntegerField(source="bank_account.id", read_only=True)
    bank_account_name = serializers.CharField(source="bank_account.name", read_only=True)
    renewal_of_id = serializers.IntegerField(
        source="renewal_of.id", read_only=True, allow_null=True
    )
    has_opening_cash_movement = serializers.SerializerMethodField()
    opening_cash_movement_id = serializers.SerializerMethodField()
    has_renewal = serializers.SerializerMethodField()
    portfolio_mismatch_warning = serializers.SerializerMethodField()

    class Meta:
        model = FixedDeposit
        fields = (
            "id",
            "portfolio_id",
            "portfolio_name",
            "bank_account_id",
            "bank_account_name",
            "institution_name",
            "deposit_account_number",
            "principal_amount",
            "currency",
            "interest_rate_percent",
            "interest_payout_frequency",
            "investment_date",
            "maturity_date",
            "nominee_name",
            "comment",
            "status",
            "renewal_of_id",
            "has_renewal",
            "has_opening_cash_movement",
            "opening_cash_movement_id",
            "portfolio_mismatch_warning",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "is_active", "created_at", "updated_at")

    def get_has_opening_cash_movement(self, obj: FixedDeposit) -> bool:
        return fixed_deposit_has_opening_cash_movement(obj.id)

    def get_opening_cash_movement_id(self, obj: FixedDeposit):
        return get_fd_opening_cash_movement_id(obj.id)

    def get_has_renewal(self, obj: FixedDeposit) -> bool:
        if hasattr(obj, "_has_renewal"):
            return bool(obj._has_renewal)
        return obj.renewals.exists()

    def get_portfolio_mismatch_warning(self, obj: FixedDeposit) -> str | None:
        return fixed_deposit_portfolio_mismatch_warning(obj)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["principal_amount"] = float(instance.principal_amount)
        data["interest_rate_percent"] = float(instance.interest_rate_percent)
        data["investment_date"] = instance.investment_date.isoformat()
        data["maturity_date"] = instance.maturity_date.isoformat()
        data["created_at"] = instance.created_at.isoformat()
        data["updated_at"] = instance.updated_at.isoformat()
        if not data.get("nominee_name"):
            data["nominee_name"] = None
        if not data.get("comment"):
            data["comment"] = None
        if not data.get("portfolio_mismatch_warning"):
            data["portfolio_mismatch_warning"] = None
        return data


class CashMovementSerializer(serializers.ModelSerializer):
    bank_account_id = serializers.IntegerField(source="bank_account.id", read_only=True)
    bank_account_name = serializers.CharField(source="bank_account.name", read_only=True)
    portfolio_id = serializers.IntegerField(
        source="portfolio.id", read_only=True, allow_null=True
    )
    signed_amount = serializers.SerializerMethodField()
    is_reversed = serializers.SerializerMethodField()
    reversed_by_id = serializers.SerializerMethodField()

    class Meta:
        model = CashMovement
        fields = (
            "id",
            "bank_account_id",
            "bank_account_name",
            "portfolio_id",
            "movement_type",
            "amount",
            "direction",
            "signed_amount",
            "currency",
            "movement_date",
            "linked_fixed_deposit_id",
            "description",
            "source",
            "is_reversal",
            "reverses_id",
            "reversal_reason",
            "is_reversed",
            "reversed_by_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_signed_amount(self, obj: CashMovement) -> float:
        from finance.bank_cash import signed_movement_amount

        return float(signed_movement_amount(obj.amount, obj.direction))

    def get_is_reversed(self, obj: CashMovement) -> bool:
        if hasattr(obj, "_is_reversed"):
            return bool(obj._is_reversed)
        return movement_has_been_reversed(obj)

    def get_reversed_by_id(self, obj: CashMovement):
        if obj.is_reversal:
            return None
        reversal = obj.reversal_rows.filter(is_reversal=True).order_by("id").first()
        return reversal.id if reversal else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["amount"] = float(instance.amount)
        data["movement_date"] = instance.movement_date.isoformat()
        data["created_at"] = instance.created_at.isoformat()
        data["updated_at"] = instance.updated_at.isoformat()
        if not data.get("description"):
            data["description"] = None
        if not data.get("reversal_reason"):
            data["reversal_reason"] = None
        return data


class ReversalWriteSerializer(serializers.Serializer):
    reversal_date = serializers.DateField(required=False, allow_null=True)
    reason = serializers.CharField()

    def validate_reason(self, value: str) -> str:
        if not (value or "").strip():
            raise serializers.ValidationError("reason is required for audit.")
        return value.strip()


class CashMovementCreateSerializer(serializers.Serializer):
    bank_account_id = serializers.IntegerField()
    movement_type = serializers.ChoiceField(choices=CashMovementType.choices)
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    movement_date = serializers.DateField()
    direction = serializers.ChoiceField(
        choices=[("CREDIT", "Credit"), ("DEBIT", "Debit")],
        required=False,
        allow_null=True,
    )
    portfolio_id = serializers.IntegerField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_movement_type(self, value: str) -> str:
        if value not in MANUAL_API_CASH_MOVEMENT_TYPES:
            raise serializers.ValidationError(
                "Only MANUAL_DEPOSIT, MANUAL_WITHDRAWAL, and ADJUSTMENT are allowed."
            )
        return value

    def validate_amount(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("amount must be greater than zero.")
        return value


class FixedDepositWriteSerializer(serializers.Serializer):
    portfolio_id = serializers.IntegerField(required=False, allow_null=True)
    bank_account_id = serializers.IntegerField()
    institution_name = serializers.CharField(max_length=255)
    deposit_account_number = serializers.CharField(max_length=128)
    principal_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    currency = serializers.CharField(max_length=3)
    interest_rate_percent = serializers.DecimalField(max_digits=8, decimal_places=4)
    interest_payout_frequency = serializers.ChoiceField(
        choices=InterestPayoutFrequency.choices
    )
    investment_date = serializers.DateField()
    maturity_date = serializers.DateField()
    nominee_name = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(
        choices=FixedDepositStatus.choices,
        required=False,
        default=FixedDepositStatus.ACTIVE,
    )
    renewal_of_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_principal_amount(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("principal_amount must be greater than zero")
        return value

    def validate_interest_rate_percent(self, value: Decimal) -> Decimal:
        if value < 0:
            raise serializers.ValidationError("interest_rate_percent must be zero or positive")
        return value

    def validate(self, attrs):
        inv = attrs.get("investment_date")
        mat = attrs.get("maturity_date")
        if inv and mat and mat <= inv:
            raise serializers.ValidationError(
                {"maturity_date": "Maturity date must be after investment date."}
            )
        return attrs


class FixedDepositUpdateSerializer(serializers.Serializer):
    portfolio_id = serializers.IntegerField(required=False)
    bank_account_id = serializers.IntegerField(required=False)
    institution_name = serializers.CharField(max_length=255, required=False)
    deposit_account_number = serializers.CharField(max_length=128, required=False)
    principal_amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False
    )
    currency = serializers.CharField(max_length=3, required=False)
    interest_rate_percent = serializers.DecimalField(
        max_digits=8, decimal_places=4, required=False
    )
    interest_payout_frequency = serializers.ChoiceField(
        choices=InterestPayoutFrequency.choices, required=False
    )
    investment_date = serializers.DateField(required=False)
    maturity_date = serializers.DateField(required=False)
    nominee_name = serializers.CharField(required=False, allow_blank=True)
    comment = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=FixedDepositStatus.choices, required=False
    )
    renewal_of_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_principal_amount(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("principal_amount must be greater than zero")
        return value

    def validate_interest_rate_percent(self, value: Decimal) -> Decimal:
        if value < 0:
            raise serializers.ValidationError("interest_rate_percent must be zero or positive")
        return value


class FixedDepositInterestPaymentSerializer(serializers.ModelSerializer):
    fixed_deposit_id = serializers.IntegerField(source="fixed_deposit.id", read_only=True)
    bank_account_id = serializers.IntegerField(source="bank_account.id", read_only=True)
    bank_account_name = serializers.CharField(source="bank_account.name", read_only=True)
    cash_movement_id = serializers.IntegerField(source="cash_movement.id", read_only=True)

    class Meta:
        model = FixedDepositInterestPayment
        fields = (
            "id",
            "fixed_deposit_id",
            "bank_account_id",
            "bank_account_name",
            "payment_date",
            "gross_interest",
            "tax_withheld",
            "net_interest",
            "currency",
            "cash_movement_id",
            "comment",
            "is_reversed",
            "reversed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["gross_interest"] = float(instance.gross_interest)
        data["tax_withheld"] = float(instance.tax_withheld)
        data["net_interest"] = float(instance.net_interest)
        data["payment_date"] = instance.payment_date.isoformat()
        data["created_at"] = instance.created_at.isoformat()
        data["updated_at"] = instance.updated_at.isoformat()
        data["reversed_at"] = (
            instance.reversed_at.isoformat() if instance.reversed_at else None
        )
        if not data.get("comment"):
            data["comment"] = None
        return data


class FixedDepositInterestPaymentWriteSerializer(serializers.Serializer):
    payment_date = serializers.DateField()
    gross_interest = serializers.DecimalField(max_digits=18, decimal_places=4)
    tax_withheld = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, default=Decimal("0")
    )
    comment = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_gross_interest(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("gross_interest must be greater than zero.")
        return value

    def validate_tax_withheld(self, value: Decimal) -> Decimal:
        if value < 0:
            raise serializers.ValidationError("tax_withheld must be zero or positive.")
        return value

    def validate(self, attrs):
        gross = attrs.get("gross_interest")
        tax = attrs.get("tax_withheld", Decimal("0"))
        if gross is not None and tax is not None and tax > gross:
            raise serializers.ValidationError(
                {"tax_withheld": "tax_withheld cannot exceed gross_interest."}
            )
        return attrs


class FixedDepositSettlementSerializer(serializers.ModelSerializer):
    fixed_deposit_id = serializers.IntegerField(source="fixed_deposit.id", read_only=True)
    fixed_deposit_status = serializers.CharField(source="fixed_deposit.status", read_only=True)
    bank_account_id = serializers.IntegerField(source="bank_account.id", read_only=True)
    bank_account_name = serializers.CharField(source="bank_account.name", read_only=True)
    principal_cash_movement_id = serializers.SerializerMethodField()
    interest_cash_movement_id = serializers.SerializerMethodField()

    class Meta:
        model = FixedDepositSettlement
        fields = (
            "id",
            "fixed_deposit_id",
            "fixed_deposit_status",
            "bank_account_id",
            "bank_account_name",
            "settlement_type",
            "settlement_date",
            "principal_returned",
            "gross_interest",
            "tax_withheld",
            "net_interest",
            "total_net_proceeds",
            "currency",
            "principal_cash_movement_id",
            "interest_cash_movement_id",
            "comment",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_principal_cash_movement_id(self, obj: FixedDepositSettlement):
        return obj.principal_cash_movement_id

    def get_interest_cash_movement_id(self, obj: FixedDepositSettlement):
        return obj.interest_cash_movement_id

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["principal_returned"] = float(instance.principal_returned)
        data["gross_interest"] = float(instance.gross_interest)
        data["tax_withheld"] = float(instance.tax_withheld)
        data["net_interest"] = float(instance.net_interest)
        data["total_net_proceeds"] = float(instance.total_net_proceeds)
        data["settlement_date"] = instance.settlement_date.isoformat()
        data["created_at"] = instance.created_at.isoformat()
        data["updated_at"] = instance.updated_at.isoformat()
        if not data.get("comment"):
            data["comment"] = None
        return data


class FixedDepositSettlementWriteSerializer(serializers.Serializer):
    settlement_type = serializers.ChoiceField(choices=FixedDepositSettlementType.choices)
    settlement_date = serializers.DateField()
    principal_returned = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, allow_null=True
    )
    gross_interest = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, default=Decimal("0")
    )
    tax_withheld = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, default=Decimal("0")
    )
    comment = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_principal_returned(self, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise serializers.ValidationError("principal_returned must be zero or positive.")
        return value

    def validate_gross_interest(self, value: Decimal) -> Decimal:
        if value < 0:
            raise serializers.ValidationError("gross_interest must be zero or positive.")
        return value

    def validate_tax_withheld(self, value: Decimal) -> Decimal:
        if value < 0:
            raise serializers.ValidationError("tax_withheld must be zero or positive.")
        return value

    def validate(self, attrs):
        gross = attrs.get("gross_interest", Decimal("0"))
        tax = attrs.get("tax_withheld", Decimal("0"))
        principal = attrs.get("principal_returned")
        if tax > gross:
            raise serializers.ValidationError(
                {"tax_withheld": "tax_withheld cannot exceed gross_interest."}
            )
        net = gross - tax
        resolved_principal = principal if principal is not None else Decimal("0")
        if resolved_principal + net <= 0 and principal is not None:
            raise serializers.ValidationError(
                "At least one of principal_returned or net_interest must be greater than zero."
            )
        return attrs


class FixedDepositCancelWriteSerializer(serializers.Serializer):
    cancellation_date = serializers.DateField(required=False, allow_null=True)


class FixedDepositRenewalWriteSerializer(serializers.Serializer):
    renewal_date = serializers.DateField()
    new_institution_name = serializers.CharField(required=False, allow_blank=True)
    new_deposit_account_number = serializers.CharField()
    new_principal_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    new_interest_rate_percent = serializers.DecimalField(max_digits=8, decimal_places=4)
    new_interest_payout_frequency = serializers.ChoiceField(
        choices=InterestPayoutFrequency.choices
    )
    new_investment_date = serializers.DateField(required=False, allow_null=True)
    new_maturity_date = serializers.DateField()
    nominee_name = serializers.CharField(required=False, allow_blank=True)
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    gross_interest = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, default=Decimal("0")
    )
    tax_withheld = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, default=Decimal("0")
    )
    cash_payout_amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, default=Decimal("0")
    )
    direct_reinvest_amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, allow_null=True
    )

    def validate_new_principal_amount(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("new_principal_amount must be greater than zero.")
        return value

    def validate_new_interest_rate_percent(self, value: Decimal) -> Decimal:
        if value < 0:
            raise serializers.ValidationError(
                "new_interest_rate_percent must be zero or positive."
            )
        return value

    def validate_gross_interest(self, value: Decimal) -> Decimal:
        if value < 0:
            raise serializers.ValidationError("gross_interest must be zero or positive.")
        return value

    def validate_tax_withheld(self, value: Decimal) -> Decimal:
        if value < 0:
            raise serializers.ValidationError("tax_withheld must be zero or positive.")
        return value

    def validate_cash_payout_amount(self, value: Decimal) -> Decimal:
        if value < 0:
            raise serializers.ValidationError("cash_payout_amount must be zero or positive.")
        return value

    def validate_direct_reinvest_amount(self, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                "direct_reinvest_amount must be greater than zero."
            )
        return value

    def validate(self, attrs):
        gross = attrs.get("gross_interest", Decimal("0"))
        tax = attrs.get("tax_withheld", Decimal("0"))
        if tax > gross:
            raise serializers.ValidationError(
                {"tax_withheld": "tax_withheld cannot exceed gross_interest."}
            )
        new_principal = attrs["new_principal_amount"]
        direct = attrs.get("direct_reinvest_amount")
        if direct is not None and direct != new_principal:
            raise serializers.ValidationError(
                {
                    "direct_reinvest_amount": (
                        "direct_reinvest_amount must match new_principal_amount "
                        "for direct rollover renewals."
                    )
                }
            )
        investment_date = attrs.get("new_investment_date") or attrs["renewal_date"]
        attrs["new_investment_date"] = investment_date
        if attrs["new_maturity_date"] <= investment_date:
            raise serializers.ValidationError(
                {"new_maturity_date": "new_maturity_date must be after new_investment_date."}
            )
        return attrs
