"""测试用例 API：视图只做编排，业务在 services/。"""
from django.http import HttpResponse
from rest_framework import status
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.testcases import serializers
from apps.testcases.models import TestCase, TestCaseVersion
from apps.testcases.services import batch as batch_service
from apps.testcases.services import cases as cases_service
from apps.testcases.services import import_export as import_export_service
from apps.testcases.services import search as search_service
from apps.testcases.services.versions import get_current_version
from common.exceptions import BusinessConflictError, NotFoundError
from common.pagination import NanoPagination
from common.permissions import HasProjectPermission


def paginate(request, queryset):
    paginator = NanoPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator, page


def case_detail_data(case):
    return serializers.TestCaseDetailSerializer(
        case, context={"version": get_current_version(case)}
    ).data


class TestCaseObjectMixin:
    """对象型路由：取用例（含软删）供权限解析与业务使用。"""

    def get_cached_object(self):
        cached = getattr(self, "_nano_case", None)
        if cached is None:
            cached = (
                TestCase.all_objects
                .select_related("project", "organization", "module", "owner", "creator")
                .prefetch_related("tags")
                .filter(pk=self.kwargs["pk"])
                .first()
            )
            if cached is None:
                raise NotFoundError("测试用例不存在")
            self._nano_case = cached
        return cached

    def get_case(self, *, allow_deleted: bool = False):
        case = self.get_cached_object()
        if case.is_deleted and not allow_deleted:
            raise NotFoundError("测试用例不存在")
        return case


class TestCaseListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]

    @property
    def permission_codename(self):
        return "testcase.create" if self.request.method == "POST" else "testcase.read"

    def get(self, request, project_id):
        queryset = search_service.build_case_queryset(request._nano_project, request.query_params)
        paginator, page = paginate(request, queryset)
        return paginator.get_paginated_response(serializers.TestCaseListSerializer(page, many=True).data)

    def post(self, request, project_id):
        serializer = serializers.TestCaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        case = cases_service.create_case(
            request._nano_project, serializer.validated_data, user=request.user, request=request
        )
        return Response(case_detail_data(case), status=status.HTTP_201_CREATED)


class TestCaseDetailView(TestCaseObjectMixin, APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    METHOD_CODENAMES = {"GET": "testcase.read", "PATCH": "testcase.update", "DELETE": "testcase.delete"}

    @property
    def permission_codename(self):
        return self.METHOD_CODENAMES.get(self.request.method, "testcase.read")

    def get(self, request, pk):
        return Response(case_detail_data(self.get_case()))

    def patch(self, request, pk):
        case = self.get_case()
        serializer = serializers.TestCaseUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        case, _version = cases_service.update_case(
            case, serializer.validated_data, user=request.user, request=request
        )
        return Response(case_detail_data(case))

    def delete(self, request, pk):
        case = self.get_case()
        cases_service.delete_case(case, user=request.user, request=request)
        return Response({"id": case.id, "case_key": case.case_key, "deleted": True})


class TestCaseRestoreView(TestCaseObjectMixin, APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.delete"

    def post(self, request, pk):
        case = self.get_cached_object()
        if not case.is_deleted:
            raise BusinessConflictError("用例未删除，无需恢复")
        cases_service.restore_case(case, user=request.user, request=request)
        return Response(case_detail_data(case))


class TestCaseDuplicateView(TestCaseObjectMixin, APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.create"

    def post(self, request, pk):
        source = self.get_case()
        new_case = cases_service.duplicate_case(source, user=request.user, request=request)
        return Response(case_detail_data(new_case), status=status.HTTP_201_CREATED)


class TestCaseMoveView(TestCaseObjectMixin, APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.update"

    def post(self, request, pk):
        case = self.get_case()
        serializer = serializers.TestCaseMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        case = cases_service.move_case(
            case, serializer.validated_data.get("module_id"), user=request.user, request=request
        )
        return Response(case_detail_data(case))


class TestCaseVersionsView(TestCaseObjectMixin, APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.read"

    def get(self, request, pk):
        case = self.get_case(allow_deleted=True)
        queryset = case.versions.select_related("created_by").order_by("-version")
        paginator, page = paginate(request, queryset)
        return paginator.get_paginated_response(
            serializers.TestCaseVersionListSerializer(page, many=True).data
        )


class TestCaseHistoryView(TestCaseObjectMixin, APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.read"

    def get(self, request, pk):
        case = self.get_case(allow_deleted=True)
        queryset = AuditLog.objects.filter(object_type="testcase", object_id=case.pk).select_related("user")
        paginator, page = paginate(request, queryset)
        return paginator.get_paginated_response(AuditLogSerializer(page, many=True).data)


class TestCaseBatchView(APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.update"

    def post(self, request, project_id):
        serializer = serializers.TestCaseBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return Response(batch_service.run_batch(
            request._nano_project,
            data["op"],
            data["test_case_ids"],
            data.get("params") or {},
            user=request.user,
            request=request,
        ))


class FileFormatNegotiation(DefaultContentNegotiation):
    """文件流接口的内容协商：`format` 查询参数表示文件格式（csv/xlsx），
    不能让 DRF 当作渲染器格式后缀解析（否则无匹配渲染器会 404）。"""

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


class TestCaseExportView(APIView):
    """导出用例（§61）：format=csv|xlsx，筛选口径与列表接口一致，返回文件流附件。"""

    permission_classes = [IsAuthenticated, HasProjectPermission]
    content_negotiation_class = FileFormatNegotiation
    permission_codename = "testcase.read"

    def get(self, request, project_id):
        fmt = request.query_params.get("format") or "xlsx"
        filename, content_type, payload = import_export_service.export_cases(
            request._nano_project, request.query_params, fmt
        )
        response = HttpResponse(payload, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class TestCaseImportView(APIView):
    """导入用例（§61）：multipart 上传 + 可选字段映射；dry_run 预览不落库，确认批量入库。"""

    permission_classes = [IsAuthenticated, HasProjectPermission]
    content_negotiation_class = FileFormatNegotiation
    permission_codename = "testcase.create"

    def post(self, request, project_id):
        serializer = serializers.TestCaseImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = import_export_service.import_cases(
            request._nano_project,
            file_name=data["file"].name,
            content=data["file"].read(),
            mapping=data.get("mapping") or {},
            dry_run=data.get("dry_run", True),
            user=request.user,
            request=request,
        )
        return Response(result)


class TestCaseVersionDetailView(APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.read"

    def get_cached_object(self):
        cached = getattr(self, "_nano_version", None)
        if cached is None:
            cached = (
                TestCaseVersion.objects
                .select_related("created_by", "test_case__project", "test_case__organization")
                .filter(pk=self.kwargs["pk"])
                .first()
            )
            if cached is None:
                raise NotFoundError("用例版本不存在")
            self._nano_version = cached
        return cached

    def get_project(self, request):
        return self.get_cached_object().test_case.project

    def get(self, request, pk):
        return Response(serializers.TestCaseVersionDetailSerializer(self.get_cached_object()).data)
