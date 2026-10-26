"""AI 请求/响应序列化器。"""
from rest_framework import serializers

from apps.ai.models import AITask
from apps.testcases.models import TestCase


class GenerateRequestSerializer(serializers.Serializer):
    requirement_id = serializers.IntegerField(required=False, allow_null=True)
    title_hint = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    count = serializers.IntegerField(min_value=1, max_value=50, default=10)
    include_edge_cases = serializers.BooleanField(default=False)
    include_security = serializers.BooleanField(default=False)
    include_compatibility = serializers.BooleanField(default=False)
    project_id = serializers.IntegerField(required=False, allow_null=True)


class ExpandRequestSerializer(serializers.Serializer):
    title_hint = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    count = serializers.IntegerField(min_value=1, max_value=50, default=5)


class DetectDuplicatesSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()


class AITaskSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = AITask
        fields = [
            "id", "task_type", "status", "model", "input_data", "output_data",
            "tokens", "duration", "error", "user", "created_at", "completed_at",
        ]
        read_only_fields = fields

    def get_user(self, obj) -> dict:
        return {"id": obj.user_id, "username": obj.user.username}


class GeneratedCasePreviewSerializer(serializers.ModelSerializer):
    """AI 用例入库后 / 入库预览共用的轻量结构。"""

    class Meta:
        model = TestCase
        fields = ["id", "case_key", "title", "priority", "case_type", "status"]
        read_only_fields = fields
