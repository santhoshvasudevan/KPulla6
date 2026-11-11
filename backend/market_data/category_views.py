from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from market_data.models import MutualFundProfile, PersonalFundCategory


class CategoryInput(serializers.Serializer):
    category = serializers.CharField(max_length=100)
    subcategory = serializers.CharField(max_length=100, allow_blank=True, required=False, default="")


class PersonalFundCategoryView(APIView):
    permission_classes = [IsAuthenticated]

    def _profile(self, user, scheme_code):
        profile = MutualFundProfile.objects.filter(
            scheme_code=scheme_code,
            asset__folios__portfolio__user=user,
        ).first()
        if profile is None:
            raise NotFound("Scheme not found in your portfolios.")
        return profile

    def get(self, request, scheme_code):
        self._profile(request.user, scheme_code)
        labels = PersonalFundCategory.objects.filter(user=request.user).order_by(
            "category", "subcategory"
        ).values("category", "subcategory").distinct()
        return Response({"labels": list(labels)})

    def put(self, request, scheme_code):
        profile = self._profile(request.user, scheme_code)
        form = CategoryInput(data=request.data)
        form.is_valid(raise_exception=True)
        PersonalFundCategory.objects.update_or_create(
            user=request.user, profile=profile, defaults=form.validated_data,
        )
        return Response(form.validated_data)

    def delete(self, request, scheme_code):
        profile = self._profile(request.user, scheme_code)
        PersonalFundCategory.objects.filter(user=request.user, profile=profile).delete()
        return Response(status=204)
