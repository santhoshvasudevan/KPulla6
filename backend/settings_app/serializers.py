from decimal import Decimal

from rest_framework import serializers

from settings_app.models import DisplayCurrency
from settings_app.services import is_valid_display_currency


class SettingsSerializer(serializers.Serializer):
    tax_rate_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        coerce_to_string=False,
    )
    display_currency = serializers.CharField(max_length=3)

    def to_representation(self, instance):
        return {
            "tax_rate_percentage": float(instance.tax_rate_percentage),
            "display_currency": instance.display_currency,
        }


class SettingsUpdateSerializer(serializers.Serializer):
    tax_rate_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        coerce_to_string=False,
    )
    display_currency = serializers.CharField(max_length=3, required=False)

    def validate_display_currency(self, value):
        normalized = (value or "").strip().upper()
        if not is_valid_display_currency(normalized):
            raise serializers.ValidationError(f"Unsupported currency: {normalized}")
        return normalized

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one field must be provided.")
        return attrs
