from decimal import Decimal

from rest_framework import serializers

from transactions.models import Transaction, TransactionType
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
            "split_from",
            "split_to",
            "portfolio_name",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for key in ("quantity", "price_per_share", "fees", "split_from", "split_to"):
            if data.get(key) is not None:
                data[key] = float(data[key])
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
            )
        except Exception as exc:
            from transactions.services import TransactionValidationError

            if isinstance(exc, TransactionValidationError):
                raise serializers.ValidationError(str(exc))
            raise
        attrs.update(validated)
        return attrs


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
