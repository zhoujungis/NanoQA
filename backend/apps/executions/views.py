"""测试执行 API 视图：业务逻辑全部在 services。"""
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.executions import serializers
from apps.executions.models import TestResult, TestRun
from apps.executions.services import defect_flow, runner
from apps.testplans.models import TestPlan
from apps.testplans.services import plans as plans_service
from common.exceptions import NotFoundError
from common.pagination import NanoPagination
from common.permissions import HasProjectPermission


class ProjectApiView(APIView):
    """按 HTTP 方法映射权限码的项目级视图基类。"""

    permission_classes = [IsAuthenticated, HasProjectPermission]
    method_permissions: dict = {}

    @property
    def permission_codename(self):
        return self.method_permissions.get(self.request.method, "")


class RunObjectMixin:
    def load_object(self) -> TestRun:
        run = (
            TestRun.objects.select_related("test_plan", "project", "organization", "created_by")
            .filter(pk=self.kwargs["run_id"])
            .first()
        )
        if run is None:
            raise NotFoundError("测试执行轮次不存在")
        return run

    def get_cached_object(self) -> TestRun:
        if getattr(self, "_run_obj", None) is None:
            self._run_obj = self.load_object()
        return self._run_obj

    def get_project(self, request):
        return self.get_cached_object().project


class ResultObjectMixin:
    def load_object(self) -> TestResult:
        result = (
            TestResult.objects.select_related(
                "test_run", "test_run__project", "test_case", "test_case_version"
            )
            .filter(pk=self.kwargs["result_id"])
            .first()
        )
        if result is None:
            raise NotFoundError("执行结果不存在")
        return result

    def get_cached_object(self) -> TestResult:
        if getattr(self, "_result_obj", None) is None:
            self._result_obj = self.load_object()
        return self._result_obj

    def get_project(self, request):
        return self.get_cached_object().test_run.project


class TestPlanRunListCreateView(ProjectApiView):
    method_permissions = {"GET": "testplan.read", "POST": "testplan.execute"}

    def _load_plan(self):
        if getattr(self, "_plan_obj", None) is None:
            plan = (
                TestPlan.objects.select_related("project", "organization")
                .filter(pk=self.kwargs["plan_id"])
                .first()
            )
            if plan is None:
                raise NotFoundError("测试计划不存在")
            self._plan_obj = plan
        return self._plan_obj

    def get_project(self, request):
        return self._load_plan().project

    def get(self, request, plan_id):
        plan = self._load_plan()
        runs = TestRun.objects.filter(test_plan=plan).select_related("created_by")
        paginator = NanoPagination()
        page = paginator.paginate_queryset(runs, request)
        data = serializers.TestRunSerializer(page, many=True).data
        return Response(paginator.get_paginated_response(data).data)

    def post(self, request, plan_id):
        plan = self._load_plan()
        serializer = serializers.TestRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run = plans_service.create_run(request, plan, dict(serializer.validated_data))
        return Response(runner.run_detail(run), status=status.HTTP_201_CREATED)


class TestRunDetailView(RunObjectMixin, ProjectApiView):
    method_permissions = {"GET": "testplan.read"}

    def get(self, request, run_id):
        return Response(runner.run_detail(self.get_cached_object()))


class TestRunResultListCreateView(RunObjectMixin, ProjectApiView):
    method_permissions = {"GET": "testplan.read", "POST": "testcase.execute"}

    def get(self, request, run_id):
        run = self.get_cached_object()
        results = TestResult.objects.filter(test_run=run).select_related(
            "test_case", "test_case__module", "test_case_version", "executed_by"
        )
        status_filter = request.query_params.get("status")
        if status_filter:
            results = results.filter(status=status_filter)
        query = request.query_params.get("q")
        if query:
            results = results.filter(
                Q(test_case__case_key__icontains=query) | Q(test_case__title__icontains=query)
            )
        paginator = NanoPagination()
        page = paginator.paginate_queryset(results, request)
        data = serializers.TestResultSerializer(page, many=True).data
        return Response(paginator.get_paginated_response(data).data)

    def post(self, request, run_id):
        run = self.get_cached_object()
        serializer = serializers.ResultSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = dict(serializer.validated_data)
        result = runner.submit_result(request, run, validated.pop("test_case_id"), validated)
        return Response(serializers.TestResultSerializer(result).data, status=status.HTTP_201_CREATED)


class TestRunResultBulkView(RunObjectMixin, ProjectApiView):
    method_permissions = {"POST": "testcase.execute"}

    def post(self, request, run_id):
        run = self.get_cached_object()
        serializer = serializers.ResultBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        results = runner.submit_results_bulk(request, run, serializer.validated_data["items"])
        data = serializers.TestResultSerializer(results, many=True).data
        return Response({"results": data, "total": len(data)}, status=status.HTTP_201_CREATED)


class TestResultDetailView(ResultObjectMixin, ProjectApiView):
    method_permissions = {"PATCH": "testcase.execute"}

    def patch(self, request, result_id):
        result = self.get_cached_object()
        serializer = serializers.ResultPatchSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        result = runner.update_result(request, result, dict(serializer.validated_data))
        return Response(serializers.TestResultSerializer(result).data)


class TestResultDefectCreateView(ResultObjectMixin, ProjectApiView):
    method_permissions = {"POST": "defect.create"}

    def post(self, request, result_id):
        result = self.get_cached_object()
        serializer = serializers.DefectFromResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        defect = defect_flow.create_defect_from_result(request, result, dict(serializer.validated_data))
        warning = None
        if result.status != "failed":
            warning = f"当前执行结果状态为 {result.status}，非失败结果，缺陷仍已创建并关联"
        return Response(
            {"defect": serializers.DefectSerializer(defect).data, "warning": warning},
            status=status.HTTP_201_CREATED,
        )
