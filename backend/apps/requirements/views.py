"""需求 API（§45 Requirements）。"""
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.requirements import serializers
from apps.requirements.models import Requirement, RequirementTestCase
from apps.requirements.services import coverage as coverage_service
from apps.requirements.services import requirements as req_service
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


class RequirementViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    serializer_class = serializers.RequirementSerializer

    ACTION_PERMISSIONS = {
        "list": "requirement.read",
        "create": "requirement.create",
        "retrieve": "requirement.read",
        "partial_update": "requirement.update",
        "destroy": "requirement.delete",
        "link_testcases": "requirement.update",
        "unlink_testcases": "requirement.update",
        "unlink_testcase": "requirement.update",
        "coverage": "requirement.read",
    }

    @property
    def permission_codename(self):
        return self.ACTION_PERMISSIONS.get(getattr(self, "action", None) or "")

    def get_cached_object(self) -> Requirement:
        if not hasattr(self, "_cached_obj"):
            obj = (
                Requirement.objects.filter(pk=self.kwargs["pk"])
                .select_related("project", "organization", "creator", "owner")
                .first()
            )
            if obj is None:
                raise NotFoundError("需求不存在")
            self._cached_obj = obj
        return self._cached_obj

    # ---------------------------------------------------------------- 列表/创建
    def list(self, request, project_id):
        project = resolve_project(request, self)
        qs = Requirement.objects.filter(project=project).select_related("owner", "creator")

        q = request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(Q(key__icontains=q) | Q(title__icontains=q) | Q(description__icontains=q))
        for param, field in (("status", "status"), ("priority", "priority")):
            value = request.query_params.get(param)
            if value:
                qs = qs.filter(**{field: value})
        owner_id = _int_param(request.query_params, "owner_id")
        if owner_id is not None:
            qs = qs.filter(owner_id=owner_id)

        page = self.paginate_queryset(qs)
        return self.get_paginated_response(serializers.RequirementSerializer(page, many=True).data)

    def create(self, request, project_id):
        project = resolve_project(request, self)
        serializer = serializers.RequirementWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requirement = req_service.create_requirement(
            project=project, user=request.user, data=serializer.validated_data, request=request
        )
        return Response(serializers.RequirementSerializer(requirement).data, status=status.HTTP_201_CREATED)

    # ---------------------------------------------------------------- 详情/更新/删除
    def retrieve(self, request, pk=None):
        requirement = self.get_cached_object()
        case_ids = RequirementTestCase.objects.filter(
            requirement=requirement, test_case__deleted_at__isnull=True
        ).values_list("test_case_id", flat=True)
        cases = TestCase.objects.filter(pk__in=case_ids)

        data = serializers.RequirementSerializer(requirement).data
        data["test_cases"] = serializers.LinkedTestCaseSerializer(cases, many=True).data
        data["coverage"] = coverage_service.requirement_coverage(requirement)
        return Response(data)

    def partial_update(self, request, pk=None):
        requirement = self.get_cached_object()
        serializer = serializers.RequirementWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        requirement = req_service.update_requirement(
            requirement=requirement,
            data=serializer.validated_data,
            expected_updated_at=request.data.get("updated_at"),
            request=request,
        )
        return Response(serializers.RequirementSerializer(requirement).data)

    def destroy(self, request, pk=None):
        requirement = self.get_cached_object()
        req_service.delete_requirement(requirement=requirement, request=request)
        return Response({"deleted": True, "key": requirement.key})

    # ---------------------------------------------------------------- 用例关联
    def link_testcases(self, request, pk=None):
        requirement = self.get_cached_object()
        test_case_ids = request.data.get("test_case_ids")
        if not isinstance(test_case_ids, list) or not test_case_ids:
            raise ValidationError("test_case_ids 必须是非空数组")
        linked = req_service.link_testcases(
            requirement=requirement, test_case_ids=test_case_ids, request=request
        )
        return Response({"linked_test_case_ids": linked})

    def unlink_testcases(self, request, pk=None):
        requirement = self.get_cached_object()
        test_case_id = request.data.get("test_case_id")
        if not isinstance(test_case_id, int):
            raise ValidationError("test_case_id 必填且必须是整数")
        req_service.unlink_testcase(requirement=requirement, test_case_id=test_case_id, request=request)
        return Response({"unlinked_test_case_id": test_case_id})

    def unlink_testcase(self, request, pk=None, case_id=None):
        requirement = self.get_cached_object()
        req_service.unlink_testcase(requirement=requirement, test_case_id=case_id, request=request)
        return Response({"unlinked_test_case_id": case_id})

    # ---------------------------------------------------------------- 覆盖率
    def coverage(self, request, pk=None):
        requirement = self.get_cached_object()
        raw = request.query_params.get("expected_cases")
        if raw in (None, ""):
            raw = request.data.get("expected_cases")
        expected = None
        if raw not in (None, ""):
            try:
                expected = int(raw)
            except (TypeError, ValueError):
                raise ValidationError("expected_cases 必须是整数")
            if expected < 1:
                raise ValidationError("expected_cases 必须 ≥ 1")
        return Response(coverage_service.requirement_coverage(requirement, expected))
