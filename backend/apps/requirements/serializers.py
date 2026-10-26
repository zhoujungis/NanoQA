"""需求序列化器。"""
from rest_framework import serializers

from apps.accounts.models import User
from apps.requirements.models import Requirement
from apps.testcases.models import TestCase


class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "display_name"]


class LinkedTestCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestCase
        fields = ["id", "case_key", "title", "priority", "status", "automation_status"]


class RequirementSerializer(serializers.ModelSerializer):
    creator = UserBriefSerializer(read_only=True)
    owner = UserBriefSerializer(read_only=True)

    class Meta:
        model = Requirement
        fields = [
            "id", "key", "title", "description", "status", "priority",
            "creator", "owner", "version", "created_at", "updated_at",
        ]
        read_only_fields = fields


class RequirementWriteSerializer(serializers.Serializer):
    """创建/更新共用；更新时传 partial=True（updated_at 由 Service 单独校验）。"""

    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Requirement.STATUS_CHOICES, required=False)
    priority = serializers.ChoiceField(choices=Requirement.PRIORITY_CHOICES, required=False)
    owner_id = serializers.PrimaryKeyRelatedField(
        source="owner", queryset=User.objects.all(), required=False, allow_null=True
    )
