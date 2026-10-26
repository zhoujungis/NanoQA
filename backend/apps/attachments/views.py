"""附件 API（§23/§53）：上传 / 下载 / 删除 / 项目内列表。"""
from django.http import FileResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.attachments import services
from apps.attachments.models import Attachment
from apps.attachments.serializers import AttachmentSerializer, AttachmentUploadSerializer
from apps.attachments.services import OBJECT_READ_PERMISSION, OBJECT_UPDATE_PERMISSION
from apps.projects.models import Project
from common.exceptions import NotFoundError
from common.pagination import NanoPagination
from common.permissions import HasProjectPermission, resolve_project
from common.storage import get_storage


class AttachmentCreateView(APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]

    def get_permissions(self):
        object_type = self.request.data.get("object_type", "")
        self.permission_codename = OBJECT_UPDATE_PERMISSION.get(object_type, "testcase.update")
        return super().get_permissions()

    def get_project(self, request):
        project_id = request.data.get("project_id")
        if not project_id:
            return None
        project = Project.objects.filter(pk=project_id).first()
        if project is None:
            raise NotFoundError("项目不存在")
        return project

    def post(self, request):
        serializer = AttachmentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        project = resolve_project(request, self)
        attachment = services.create_attachment(
            file=data["file"],
            object_type=data["object_type"],
            object_id=data["object_id"],
            project=project,
            user=request.user,
            request=request,
        )
        return Response(AttachmentSerializer(attachment).data)


class AttachmentDetailView(APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_map = OBJECT_READ_PERMISSION

    def get_cached_object(self) -> Attachment:
        if not hasattr(self, "_attachment"):
            attachment = Attachment.objects.filter(pk=self.kwargs["pk"]).select_related("project").first()
            if attachment is None:
                raise NotFoundError("附件不存在")
            self._attachment = attachment
        return self._attachment

    def get_permissions(self):
        self.permission_codename = self.permission_map.get(
            self.get_cached_object().object_type, "testcase.read"
        )
        return super().get_permissions()

    def get(self, request, pk):
        attachment = self.get_cached_object()
        resolve_project(request, self)
        handle = get_storage().open(attachment.storage_key)
        # FileResponse(as_attachment=True, filename=...) 自动做 RFC5987 编码，中文文件名安全
        return FileResponse(
            handle,
            content_type=attachment.mime_type or "application/octet-stream",
            as_attachment=True,
            filename=attachment.filename,
        )


class AttachmentDeleteView(AttachmentDetailView):
    permission_map = OBJECT_UPDATE_PERMISSION

    def delete(self, request, pk):
        attachment = self.get_cached_object()
        resolve_project(request, self)
        services.delete_attachment(attachment, request=request)
        return Response({"deleted": True, "id": attachment.id})


class ProjectAttachmentListView(APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.read"

    def get(self, request, project_id):
        project = resolve_project(request, self)
        queryset = Attachment.objects.filter(project=project).select_related("uploaded_by")
        object_type = request.query_params.get("object_type")
        if object_type:
            queryset = queryset.filter(object_type=object_type)
        object_id = request.query_params.get("object_id")
        if object_id:
            queryset = queryset.filter(object_id=object_id)
        paginator = NanoPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(AttachmentSerializer(page, many=True).data)
