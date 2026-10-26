"""附件路由（§53）：/api/v1/ 前缀由 config.urls 挂载。"""
from django.urls import path

from apps.attachments.views import (
    AttachmentCreateView,
    AttachmentDeleteView,
    AttachmentDetailView,
    ProjectAttachmentListView,
)

urlpatterns = [
    path("attachments/", AttachmentCreateView.as_view(), name="attachment-create"),
    path("attachments/<int:pk>/download/", AttachmentDetailView.as_view(), name="attachment-download"),
    path("attachments/<int:pk>/", AttachmentDeleteView.as_view(), name="attachment-delete"),
    path("projects/<int:project_id>/attachments/", ProjectAttachmentListView.as_view(), name="attachment-list"),
]
