from django.db import connection
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """GET /api/v1/health — service and database connectivity check."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        db_status = "ok"
        try:
            connection.ensure_connection()
        except Exception:
            db_status = "unavailable"

        http_status = (
            status.HTTP_200_OK
            if db_status == "ok"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response(
            {
                "status": "ok" if db_status == "ok" else "degraded",
                "service": "kpulla6",
                "database": db_status,
            },
            status=http_status,
        )
