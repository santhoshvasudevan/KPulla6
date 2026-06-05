from rest_framework import serializers

from portfolios.models import Portfolio


class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields = (
            "id",
            "name",
            "description",
            "base_currency",
            "is_default",
            "is_active",
            "cash_aware_enabled",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class PortfolioCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    base_currency = serializers.CharField(max_length=3, required=False, default="EUR")
    cash_aware_enabled = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Omitted → true. Send false to create a legacy-mode portfolio.",
    )


class PortfolioUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    base_currency = serializers.CharField(max_length=3, required=False)
    is_active = serializers.BooleanField(required=False)
    cash_aware_enabled = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one field must be provided.")
        return attrs
