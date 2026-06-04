from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from settings_app.serializers import SettingsSerializer, SettingsUpdateSerializer
from settings_app.services import get_settings, update_settings


class SettingsView(APIView):
    def get(self, request):
        settings = get_settings(request.user)
        return Response(SettingsSerializer(settings).data)

    def put(self, request):
        serializer = SettingsUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        settings = update_settings(request.user, **serializer.validated_data)
        return Response(SettingsSerializer(settings).data)
