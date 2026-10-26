"""测试计划序列化器（§16-17）。"""
from rest_framework import serializers

from apps.accounts.models import User
from apps.testplans.models import TestPlan, TestPlanCase


class TestPlanSerializer(serializers.ModelSerializer):
    owner_id = serializers.PrimaryKeyRelatedField(
        source="owner", queryset=User.objects.all(), allow_null=True, required=False
    )
    owner_name = serializers.CharField(source="owner.display_name", read_only=True, default=None)
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True, default=None)
    status = serializers.ChoiceField(choices=TestPlan.STATUS_CHOICES, required=False)

    class Meta:
        model = TestPlan
        fields = [
            "id", "organization", "project", "name", "description", "version", "status",
            "start_at", "end_at", "owner_id", "owner_name", "created_by", "created_by_name",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "organization", "project", "created_by", "created_by_name",
            "owner_name", "created_at", "updated_at",
        ]


class TestPlanCaseSerializer(serializers.ModelSerializer):
    case_key = serializers.CharField(source="test_case.case_key", read_only=True)
    title = serializers.CharField(source="test_case.title", read_only=True)
    module_name = serializers.CharField(source="test_case.module.name", read_only=True, default=None)
    assigned_to_name = serializers.CharField(source="assigned_to.display_name", read_only=True, default=None)
    priority = serializers.ChoiceField(choices=["P0", "P1", "P2", "P3"], required=False)

    class Meta:
        model = TestPlanCase
        fields = [
            "id", "test_case", "case_key", "title", "module_name",
            "priority", "assigned_to", "assigned_to_name", "execution_status",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "test_case", "case_key", "title", "module_name", "execution_status",
            "created_at", "updated_at",
        ]


class PlanCaseAddSerializer(serializers.Serializer):
    test_case_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), allow_null=True, required=False
    )


class PlanCaseUpdateSerializer(serializers.Serializer):
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), allow_null=True, required=False
    )
    priority = serializers.ChoiceField(choices=["P0", "P1", "P2", "P3"], required=False)
