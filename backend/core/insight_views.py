from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .finance_serializers import ReportInput
from .finance_views import validated
from .insights import insights
from .views import TenantMixin


class Insights(TenantMixin, APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "business_reports"
    @extend_schema(parameters=[ReportInput], responses={200: dict})
    def get(self, request, business_id):
        return Response(insights(self.business, **validated(ReportInput, request.query_params)))
