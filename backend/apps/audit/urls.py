from django.urls import path

from apps.audit.views import AuditLogViewSet

urlpatterns = [
    path("projects/<int:project_id>/audit-logs/", AuditLogViewSet.as_view({"get": "list"}), name="auditlog-list"),
]
