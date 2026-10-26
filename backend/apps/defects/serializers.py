"""缺陷序列化器。"""
from rest_framework import serializers

from apps.accounts.models import User
from apps.defects.models import Defect
from apps.executions.models import TestResult
from apps.requirements.models import Requirement
from apps.testcases.models import TestCase


class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "display_name"]


class LinkedTestCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestCase
        fields = ["id", "case_key", "title", "priority", "status"]


class LinkedRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Requirement
        fields = ["id", "key", "title", "status", "priority"]


class DefectTestResultSerializer(serializers.ModelSerializer):
    test_case_key = serializers.CharField(source="test_case.case_key", read_only=True)
    test_case_title = serializers.CharField(source="test_case.title", read_only=True)
    test_run_name = serializers.CharField(source="test_run.name", read_only=True)

    class Meta:
        model = TestResult
        fields = [
            "id", "test_case", "test_case_key", "test_case_title",
            "test_run", "test_run_name", "status", "executed_at", "duration", "comment",
        ]


class DefectSerializer(serializers.ModelSerializer):
    assignee = UserBriefSerializer(read_only=True)
    reporter = UserBriefSerializer(read_only=True)

    class Meta:
        model = Defect
        fields = [
            "id", "key", "title", "description", "severity", "priority", "status",
            "environment", "version", "assignee", "reporter",
            "resolved_at", "closed_at", "created_at", "updated_at",
        ]
        read_only_fields = fields


class DefectCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    severity = serializers.ChoiceField(choices=Defect.SEVERITY_CHOICES, required=False)
    priority = serializers.ChoiceField(choices=Defect.PRIORITY_CHOICES, required=False)
    environment = serializers.CharField(required=False, allow_blank=True, max_length=64)
    version = serializers.CharField(required=False, allow_blank=True, max_length=64)
    assignee_id = serializers.PrimaryKeyRelatedField(
        source="assignee", queryset=User.objects.all(), required=False, allow_null=True
    )
    test_case_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    requirement_ids = serializers.ListField(child=serializers.IntegerField(), required=False)


class DefectUpdateSerializer(serializers.Serializer):
    """更新时传 partial=True（updated_at 由 Service 单独校验）。"""

    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    severity = serializers.ChoiceField(choices=Defect.SEVERITY_CHOICES, required=False)
    priority = serializers.ChoiceField(choices=Defect.PRIORITY_CHOICES, required=False)
    status = serializers.ChoiceField(choices=Defect.STATUS_CHOICES, required=False)
    environment = serializers.CharField(required=False, allow_blank=True, max_length=64)
    version = serializers.CharField(required=False, allow_blank=True, max_length=64)
    assignee_id = serializers.PrimaryKeyRelatedField(
        source="assignee", queryset=User.objects.all(), required=False, allow_null=True
    )
