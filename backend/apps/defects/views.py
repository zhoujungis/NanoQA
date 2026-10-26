"""缺陷 API（§45 Defects）。"""
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.defects import serializers
from apps.defects.models import Defect, RequirementDefect, TestCaseDefect, TestResultDefect
from apps.defects.services import defects as defect_service
from apps.executions.models import TestResult
from apps.requirements.models import Requirement
from apps.testcases.models import TestCase
from common.exceptions import NotFoundError
from common.permissions import HasProjectPermission, resolve_project


def _int_param(params, name):
    value = params.get(name)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} 必须是整数")


class DefectViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    serializer_class = serializers.DefectSerializer

    ACTION_PERMISSIONS = {
        "list": "defect.read",
        "create": "defect.create",
        "retrieve": "defect.read",
        "partial_update": "defect.update",
        "destroy": "defect.delete",
        "link_testcases": "defect.update",
        "unlink_testcase": "defect.update",
        "link_requirements": "defect.update",
        "unlink_requirement": "defect.update",
    }

    @property
    def permission_codename(self):
        return self.ACTION_PERMISSIONS.get(getattr(self, "action", None) or "")

    def get_cached_object(self) -> Defect:
        if not hasattr(self, "_cached_obj"):
            obj = (
                Defect.objects.filter(pk=self.kwargs["pk"])
                .select_related("project", "organization", "reporter", "assignee")
                .first()
            )
            if obj is None:
                raise NotFoundError("缺陷不存在")
            self._cached_obj = obj
        return self._cached_obj

    # ---------------------------------------------------------------- 列表/创建
    def list(self, request, project_id):
        project = resolve_project(request, self)
        qs = Defect.objects.filter(project=project).select_related("assignee", "reporter")

        q = request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(Q(key__icontains=q) | Q(title__icontains=q) | Q(description__icontains=q))
        for param, field in (
            ("status", "status"), ("severity", "severity"), ("priority", "priority")
        ):
            value = request.query_params.get(param)
            if value:
                qs = qs.filter(**{field: value})
        assignee_id = _int_param(request.query_params, "assignee_id")
        if assignee_id is not None:
            qs = qs.filter(assignee_id=assignee_id)
        reporter_id = _int_param(request.query_params, "reporter_id")
        if reporter_id is not None:
            qs = qs.filter(reporter_id=reporter_id)

        page = self.paginate_queryset(qs)
        return self.get_paginated_response(serializers.DefectSerializer(page, many=True).data)

    def create(self, request, project_id):
        project = resolve_project(request, self)
        serializer = serializers.DefectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        defect = defect_service.create_defect(
            project=project, user=request.user, data=serializer.validated_data, request=request
        )
        return Response(serializers.DefectSerializer(defect).data, status=status.HTTP_201_CREATED)

    # ---------------------------------------------------------------- 详情/更新/归档
    def retrieve(self, request, pk=None):
        defect = self.get_cached_object()
        case_ids = list(TestCaseDefect.objects.filter(defect=defect).values_list("test_case_id", flat=True))
        req_ids = list(RequirementDefect.objects.filter(defect=defect).values_list("requirement_id", flat=True))
        result_ids = list(TestResultDefect.objects.filter(defect=defect).values_list("test_result_id", flat=True))

        data = serializers.DefectSerializer(defect).data
        data["test_cases"] = serializers.LinkedTestCaseSerializer(
            TestCase.objects.filter(pk__in=case_ids, deleted_at__isnull=True), many=True
        ).data
        data["requirements"] = serializers.LinkedRequirementSerializer(
            Requirement.objects.filter(pk__in=req_ids, deleted_at__isnull=True), many=True
        ).data
        data["test_results"] = serializers.DefectTestResultSerializer(
            TestResult.objects.filter(pk__in=result_ids).select_related("test_case", "test_run"),
            many=True,
        ).data
        data["timeline"] = defect_service.defect_timeline(defect)
        return Response(data)

    def partial_update(self, request, pk=None):
        defect = self.get_cached_object()
        serializer = serializers.DefectUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        defect = defect_service.update_defect(
            defect=defect,
            data=serializer.validated_data,
            expected_updated_at=request.data.get("updated_at"),
            request=request,
        )
        return Response(serializers.DefectSerializer(defect).data)

    def destroy(self, request, pk=None):
        defect = self.get_cached_object()
        defect_service.archive_defect(defect=defect, user=request.user, request=request)
        return Response({"archived": True, "key": defect.key, "status": defect.status})

    # ---------------------------------------------------------------- 关联
    def link_testcases(self, request, pk=None):
        defect = self.get_cached_object()
        test_case_ids = request.data.get("test_case_ids")
        if not isinstance(test_case_ids, list) or not test_case_ids:
            raise ValidationError("test_case_ids 必须是非空数组")
        linked = defect_service.link_testcases(defect=defect, test_case_ids=test_case_ids, request=request)
        return Response({"linked_test_case_ids": linked})

    def unlink_testcase(self, request, pk=None, case_id=None):
        defect = self.get_cached_object()
        defect_service.unlink_testcase(defect=defect, test_case_id=case_id, request=request)
        return Response({"unlinked_test_case_id": case_id})

    def link_requirements(self, request, pk=None):
        defect = self.get_cached_object()
        requirement_ids = request.data.get("requirement_ids")
        if not isinstance(requirement_ids, list) or not requirement_ids:
            raise ValidationError("requirement_ids 必须是非空数组")
        linked = defect_service.link_requirements(
            defect=defect, requirement_ids=requirement_ids, request=request
        )
        return Response({"linked_requirement_ids": linked})

    def unlink_requirement(self, request, pk=None, req_id=None):
        defect = self.get_cached_object()
        defect_service.unlink_requirement(defect=defect, requirement_id=req_id, request=request)
        return Response({"unlinked_requirement_id": req_id})
