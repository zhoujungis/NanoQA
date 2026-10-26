"""AI API（§39-§43）：生成/评审/扩展/重复检测/需求与缺陷分析，输出只进 AITask（坑 3）。"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai import serializers
from apps.ai.models import AITask
from apps.ai.services import duplicate_detector, risk_analyzer, tasks, testcase_generator, testcase_reviewer
from apps.ai.services.tasks import AITaskFailed
from apps.defects.models import Defect
from apps.projects.models import Project
from apps.requirements.models import Requirement
from apps.testcases.models import TestCase
from common.exceptions import CODE_VALIDATION_ERROR, NanoAPIError, NotFoundError
from common.pagination import NanoPagination
from common.permissions import HasProjectPermission, resolve_project
from common.renderers import envelope

TASK_GENERATE = "generate_testcases"
TASK_REVIEW = "review_testcase"
TASK_EXPAND = "expand_edge_cases"
TASK_DUPLICATES = "detect_duplicate_cases"
TASK_REQUIREMENT = "analyze_requirement"
TASK_DEFECT = "analyze_defect"


def _failure_response(exc: AITaskFailed) -> Response:
    return Response(
        envelope(CODE_VALIDATION_ERROR, str(exc), {
            "task_id": exc.task.id, "status": exc.task.status, "error": exc.task.error,
        }),
        status=400,
    )


class TargetObjectMixin:
    """按路径对象解析项目上下文；对象即权限边界（§70）。"""

    target_model = None
    target_kwarg = ""
    target_label = "资源"

    def get_target(self):
        if not hasattr(self, "_target"):
            obj = self.target_model.objects.filter(pk=self.kwargs[self.target_kwarg]).first()
            if obj is None:
                raise NotFoundError(f"{self.target_label}不存在")
            self._target = obj
        return self._target

    def get_project(self, request):
        return self.get_target().project


class GenerateTestcasesView(APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.create"

    def get_project(self, request):
        requirement_id = request.data.get("requirement_id")
        if requirement_id:
            requirement = Requirement.objects.filter(pk=requirement_id).first()
            if requirement is None:
                raise NotFoundError("需求不存在")
            project_id = request.data.get("project_id")
            if project_id and int(project_id) != requirement.project_id:
                raise NanoAPIError("需求与项目不匹配")
            return requirement.project
        project_id = request.data.get("project_id")
        if not project_id:
            return None
        project = Project.objects.filter(pk=project_id).first()
        if project is None:
            raise NotFoundError("项目不存在")
        return project

    def post(self, request):
        serializer = serializers.GenerateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        project = resolve_project(request, self)

        title, description = data.get("title_hint") or "核心功能", ""
        if data.get("requirement_id"):
            requirement = Requirement.objects.get(pk=data["requirement_id"])
            title = data.get("title_hint") or requirement.title
            description = requirement.description

        try:
            task = tasks.run_task(
                project=project,
                user=request.user,
                task_type=TASK_GENERATE,
                input_data=dict(data),
                produce=lambda provider: testcase_generator.generate_cases(
                    provider,
                    title=title,
                    description=description,
                    count=data.get("count", 10),
                    include_edge_cases=data.get("include_edge_cases", False),
                    include_security=data.get("include_security", False),
                    include_compatibility=data.get("include_compatibility", False),
                ),
            )
        except AITaskFailed as exc:
            return _failure_response(exc)

        return Response({
            "task_id": task.id,
            "status": task.status,
            "cases": task.output_data.get("cases", []),
        })


class DetectDuplicatesView(APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.read"

    def get_project(self, request):
        project_id = request.data.get("project_id")
        if not project_id:
            return None
        project = Project.objects.filter(pk=project_id).first()
        if project is None:
            raise NotFoundError("项目不存在")
        return project

    def post(self, request):
        serializer = serializers.DetectDuplicatesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = resolve_project(request, self)

        try:
            task = tasks.run_task(
                project=project,
                user=request.user,
                task_type=TASK_DUPLICATES,
                input_data={"project_id": project.id},
                produce=lambda provider: {"pairs": duplicate_detector.find_duplicates(project)},
            )
        except AITaskFailed as exc:
            return _failure_response(exc)

        return Response({"task_id": task.id, "status": task.status, "pairs": task.output_data.get("pairs", [])})


class ReviewCaseView(TargetObjectMixin, APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.review"
    target_model = TestCase
    target_kwarg = "case_id"
    target_label = "测试用例"

    def post(self, request, case_id):
        test_case = self.get_target()
        try:
            task = tasks.run_task(
                project=test_case.project,
                user=request.user,
                task_type=TASK_REVIEW,
                input_data={"test_case_id": test_case.id},
                produce=lambda provider: testcase_reviewer.review_case(provider, test_case),
            )
        except AITaskFailed as exc:
            return _failure_response(exc)

        return Response({
            "task_id": task.id,
            "status": task.status,
            **{key: task.output_data[key] for key in ("score", "issues", "suggestions")},
        })


class ExpandCaseView(TargetObjectMixin, APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.create"
    target_model = TestCase
    target_kwarg = "case_id"
    target_label = "测试用例"

    def post(self, request, case_id):
        test_case = self.get_target()
        serializer = serializers.ExpandRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        version = test_case.versions.order_by("-version").first()
        description = version.description if version else ""

        try:
            task = tasks.run_task(
                project=test_case.project,
                user=request.user,
                task_type=TASK_EXPAND,
                input_data={"test_case_id": test_case.id, **dict(data)},
                produce=lambda provider: testcase_generator.expand_edge_cases(
                    provider,
                    title=data.get("title_hint") or test_case.title,
                    description=description,
                    count=data.get("count", 5),
                ),
            )
        except AITaskFailed as exc:
            return _failure_response(exc)

        return Response({
            "task_id": task.id,
            "status": task.status,
            "cases": task.output_data.get("cases", []),
        })


class AnalyzeRequirementView(TargetObjectMixin, APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "requirement.read"
    target_model = Requirement
    target_kwarg = "requirement_id"
    target_label = "需求"

    def post(self, request, requirement_id):
        requirement = self.get_target()
        try:
            task = tasks.run_task(
                project=requirement.project,
                user=request.user,
                task_type=TASK_REQUIREMENT,
                input_data={"requirement_id": requirement.id},
                produce=lambda provider: risk_analyzer.analyze_requirement(provider, requirement),
            )
        except AITaskFailed as exc:
            return _failure_response(exc)

        return Response({"task_id": task.id, "status": task.status, **task.output_data})


class AnalyzeDefectView(TargetObjectMixin, APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "defect.read"
    target_model = Defect
    target_kwarg = "defect_id"
    target_label = "缺陷"

    def post(self, request, defect_id):
        defect = self.get_target()
        related_case_ids = list(defect.testcasedefect_set.values_list("test_case_id", flat=True))
        try:
            task = tasks.run_task(
                project=defect.project,
                user=request.user,
                task_type=TASK_DEFECT,
                input_data={"defect_id": defect.id},
                produce=lambda provider: risk_analyzer.analyze_defect(provider, defect, related_case_ids),
            )
        except AITaskFailed as exc:
            return _failure_response(exc)

        return Response({"task_id": task.id, "status": task.status, **task.output_data})


class AITaskListView(APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.read"

    def get_project(self, request):
        project_id = request.query_params.get("project_id")
        if not project_id:
            return None
        project = Project.objects.filter(pk=project_id).first()
        if project is None:
            raise NotFoundError("项目不存在")
        return project

    def get(self, request):
        project = resolve_project(request, self)
        queryset = AITask.objects.filter(project=project).select_related("user")
        task_type = request.query_params.get("task_type")
        if task_type:
            queryset = queryset.filter(task_type=task_type)
        paginator = NanoPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(serializers.AITaskSerializer(page, many=True).data)


class AITaskDetailView(TargetObjectMixin, APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.read"
    target_model = AITask
    target_kwarg = "task_id"
    target_label = "AI 任务"

    def get(self, request, task_id):
        return Response(serializers.AITaskSerializer(self.get_target()).data)


class AcceptTaskView(TargetObjectMixin, APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.review"
    target_model = AITask
    target_kwarg = "task_id"
    target_label = "AI 任务"

    def post(self, request, task_id):
        created = tasks.accept_task(self.get_target(), request.user, request=request)
        return Response({
            "task_id": self.get_target().id,
            "cases": serializers.GeneratedCasePreviewSerializer(created, many=True).data,
        })


class RejectTaskView(TargetObjectMixin, APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.review"
    target_model = AITask
    target_kwarg = "task_id"
    target_label = "AI 任务"

    def post(self, request, task_id):
        task = tasks.reject_task(self.get_target(), request.user, request=request)
        return Response({"task_id": task.id, "status": task.status, "rejected": True})
