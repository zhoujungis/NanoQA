"""审计日志查询 API。"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from common.permissions import HasProjectPermission


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "audit.read"

    def get_project(self, request):
        from apps.projects.models import Project
        return Project.objects.get(pk=self.kwargs["project_id"])

    def get_queryset(self):
        return (
            AuditLog.objects.filter(project_id=self.kwargs["project_id"])
            .select_related("user")
        )
