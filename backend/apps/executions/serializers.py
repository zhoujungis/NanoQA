"""执行序列化器（§18-21）：TestRun / TestResult / 建缺陷入参。"""
from rest_framework import serializers

from apps.defects.models import Defect
from apps.executions.models import TestResult, TestRun

RESULT_STATUSES = ["passed", "failed", "blocked", "skipped"]


class TestRunSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True, default=None)

    class Meta:
        model = TestRun
        fields = [
            "id", "test_plan", "name", "environment", "build_version", "status",
            "started_at", "finished_at", "created_by", "created_by_name",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class TestResultSerializer(serializers.ModelSerializer):
    case_key = serializers.CharField(source="test_case.case_key", read_only=True)
    title = serializers.CharField(source="test_case.title", read_only=True)
    module = serializers.CharField(source="test_case.module.name", read_only=True, default=None)
    case_version = serializers.IntegerField(source="test_case_version.version", read_only=True)
    executed_by_name = serializers.CharField(source="executed_by.display_name", read_only=True, default=None)

    class Meta:
        model = TestResult
        fields = [
            "id", "test_run", "test_case", "case_key", "title", "module",
            "test_case_version", "case_version",
            "status", "actual_result", "comment",
            "executed_by", "executed_by_name", "executed_at", "duration",
        ]
        read_only_fields = fields


class TestRunCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128, required=False, allow_blank=True)
    environment = serializers.CharField(max_length=64, required=False, allow_blank=True)
    build_version = serializers.CharField(max_length=64, required=False, allow_blank=True)


class ResultSubmitSerializer(serializers.Serializer):
    test_case_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=RESULT_STATUSES)
    actual_result = serializers.CharField(required=False, allow_blank=True)
    comment = serializers.CharField(required=False, allow_blank=True)
    duration = serializers.IntegerField(required=False, min_value=0)


class ResultBulkSerializer(serializers.Serializer):
    items = ResultSubmitSerializer(many=True, allow_empty=False)


class ResultPatchSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=RESULT_STATUSES + ["not_run"], required=False)
    actual_result = serializers.CharField(required=False, allow_blank=True)
    comment = serializers.CharField(required=False, allow_blank=True)
    duration = serializers.IntegerField(required=False, min_value=0)


class DefectFromResultSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    severity = serializers.ChoiceField(choices=Defect.SEVERITY_CHOICES, required=False)
    priority = serializers.ChoiceField(choices=Defect.PRIORITY_CHOICES, required=False)
    environment = serializers.CharField(max_length=64, required=False, allow_blank=True)
    version = serializers.CharField(max_length=64, required=False, allow_blank=True)
    comment = serializers.CharField(required=False, allow_blank=True)


class DefectSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(source="reporter.display_name", read_only=True, default=None)

    class Meta:
        model = Defect
        fields = [
            "id", "key", "title", "description", "severity", "priority", "status",
            "environment", "version", "reporter", "reporter_name", "assignee",
            "resolved_at", "closed_at", "created_at", "updated_at",
        ]
        read_only_fields = fields
