"""测试计划 API 视图：业务逻辑全部在 services。"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.executions.serializers import TestRunCreateSerializer
from apps.executions.services.runner import run_detail
from apps.testplans import serializers
from apps.testplans.models import TestPlan
from apps.testplans.services import plans as plans_service
from common.exceptions import NotFoundError
from common.pagination import NanoPagination
from common.permissions import HasProjectPermission, resolve_project


class ProjectApiView(APIView):
    """按 HTTP 方法映射权限码的项目级视图基类。"""

    permission_classes = [IsAuthenticated, HasProjectPermission]
    method_permissions: dict = {}

    @property
    def permission_codename(self):
        return self.method_permissions.get(self.request.method, "")


class PlanObjectMixin:
    def load_object(self) -> TestPlan:
        plan = (
            TestPlan.objects.select_related("project", "organization", "owner", "created_by")
            .filter(pk=self.kwargs["plan_id"])
            .first()
        )
        if plan is None:
            raise NotFoundError("测试计划不存在")
        return plan

    def get_cached_object(self) -> TestPlan:
        if getattr(self, "_plan_obj", None) is None:
            self._plan_obj = self.load_object()
        return self._plan_obj

    def get_project(self, request):
        return self.get_cached_object().project


class ProjectTestPlanListCreateView(ProjectApiView):
    method_permissions = {"GET": "testplan.read", "POST": "testplan.create"}

    def get(self, request, project_id):
        project = resolve_project(request, self)
        plans = TestPlan.objects.filter(project=project).select_related("owner", "created_by")
        paginator = NanoPagination()
        page = paginator.paginate_queryset(plans, request)
        data = serializers.TestPlanSerializer(page, many=True).data
        return Response(paginator.get_paginated_response(data).data)

    def post(self, request, project_id):
        project = resolve_project(request, self)
        serializer = serializers.TestPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = plans_service.create_plan(request, project, serializer.validated_data)
        return Response(serializers.TestPlanSerializer(plan).data, status=status.HTTP_201_CREATED)


class TestPlanDetailView(PlanObjectMixin, ProjectApiView):
    method_permissions = {"GET": "testplan.read", "PATCH": "testplan.update", "DELETE": "testplan.delete"}

    def get(self, request, plan_id):
        plan = self.get_cached_object()
        data = serializers.TestPlanSerializer(plan).data
        cases = plan.plan_cases.select_related("test_case", "test_case__module", "assigned_to")
        data["cases"] = serializers.TestPlanCaseSerializer(cases, many=True).data
        return Response(data)

    def patch(self, request, plan_id):
        plan = self.get_cached_object()
        serializer = serializers.TestPlanSerializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        plan = plans_service.update_plan(
            request, plan, dict(serializer.validated_data), request.data.get("updated_at")
        )
        return Response(serializers.TestPlanSerializer(plan).data)

    def delete(self, request, plan_id):
        plan = self.get_cached_object()
        plans_service.cancel_plan(request, plan)
        return Response({"deleted": True, "status": plan.status})


class TestPlanCaseListCreateView(PlanObjectMixin, ProjectApiView):
    method_permissions = {"POST": "testplan.update"}

    def post(self, request, plan_id):
        plan = self.get_cached_object()
        serializer = serializers.PlanCaseAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = plans_service.add_cases(
            request, plan,
            serializer.validated_data["test_case_ids"],
            serializer.validated_data.get("assigned_to"),
        )
        return Response(result, status=status.HTTP_201_CREATED)


class TestPlanCaseDetailView(PlanObjectMixin, ProjectApiView):
    method_permissions = {"PATCH": "testplan.update", "DELETE": "testplan.update"}

    def patch(self, request, plan_id, case_id):
        plan = self.get_cached_object()
        serializer = serializers.PlanCaseUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        link = plans_service.update_plan_case(request, plan, case_id, dict(serializer.validated_data))
        return Response(serializers.TestPlanCaseSerializer(link).data)

    def delete(self, request, plan_id, case_id):
        plan = self.get_cached_object()
        plans_service.remove_plan_case(request, plan, case_id)
        return Response({"deleted": True, "test_case_id": case_id})


class TestPlanStartView(PlanObjectMixin, ProjectApiView):
    method_permissions = {"POST": "testplan.execute"}

    def post(self, request, plan_id):
        plan = self.get_cached_object()
        serializer = TestRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run = plans_service.start_plan(request, plan, dict(serializer.validated_data))
        return Response(run_detail(run), status=status.HTTP_201_CREATED)
