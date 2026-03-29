from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.audit.models import AuditLog
from apps.organizations.mixins import OrganizationContextMixin
from apps.organizations.permissions import HasOrganization, IsOwner

from ..pagination import AuditPagination
from .serializers import AuditLogSerializer


class AuditLogListView(OrganizationContextMixin, ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, HasOrganization, IsOwner]
    pagination_class = AuditPagination

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_fields = ["action"]
    search_fields = ["actor__email", "action"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return AuditLog.objects.filter(
            organization=self.request.organization
        ).select_related("actor")
