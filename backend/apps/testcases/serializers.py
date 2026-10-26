"""测试用例序列化器：输入校验（steps 结构 / 枚举）+ 输出（避免 N+1）。"""
import json

from rest_framework import serializers

from apps.projects.models import Tag
from apps.testcases.models import TestCase, TestCaseVersion


class IsoDateTimeField(serializers.DateTimeField):
    """ISO 微秒输出；写入原样透传，由乐观锁（common.optimistic）解析比对。"""

    def to_representation(self, value):
        if value is None:
            return None
        return value.isoformat(timespec="microseconds")

    def to_internal_value(self, value):
        return value


class UserBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)


class TagBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "color"]


def normalize_steps(value) -> list[dict]:
    """steps 必须是非空列表，每项含非空 action 与 expected；order 自动重排 1..n。"""
    if not isinstance(value, list) or not value:
        raise serializers.ValidationError("steps 必须是非空列表")
    steps = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise serializers.ValidationError(f"steps[{index}] 必须是对象")
        action = item.get("action")
        expected = item.get("expected")
        if not isinstance(action, str) or not action.strip():
            raise serializers.ValidationError(f"steps[{index}].action 必须是非空文本")
        if not isinstance(expected, str) or not expected.strip():
            raise serializers.ValidationError(f"steps[{index}].expected 必须是非空文本")
        steps.append({"order": index + 1, "action": action, "expected": expected})
    return steps


class TestCaseCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    module_id = serializers.IntegerField(required=False, allow_null=True)
    priority = serializers.ChoiceField(choices=TestCase.PRIORITY_CHOICES)
    case_type = serializers.ChoiceField(choices=TestCase.TYPE_CHOICES, required=False)
    precondition = serializers.CharField(required=False, allow_blank=True)
    steps = serializers.JSONField()
    expected_result = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    owner_id = serializers.IntegerField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=[TestCase.STATUS_DRAFT, TestCase.STATUS_ACTIVE], required=False)

    def validate_steps(self, value):
        return normalize_steps(value)


class TestCaseUpdateSerializer(serializers.Serializer):
    updated_at = IsoDateTimeField(required=False)  # 乐观锁：客户端原样回传
    title = serializers.CharField(max_length=255, required=False)
    module_id = serializers.IntegerField(required=False, allow_null=True)
    priority = serializers.ChoiceField(choices=TestCase.PRIORITY_CHOICES, required=False)
    case_type = serializers.ChoiceField(choices=TestCase.TYPE_CHOICES, required=False)
    precondition = serializers.CharField(required=False, allow_blank=True)
    steps = serializers.JSONField(required=False)
    expected_result = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    change_summary = serializers.CharField(required=False, allow_blank=True, max_length=255)
    tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    owner_id = serializers.IntegerField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=TestCase.STATUS_CHOICES, required=False)
    automation_status = serializers.ChoiceField(choices=TestCase.AUTOMATION_CHOICES, required=False)
    automation_framework = serializers.CharField(required=False, allow_blank=True, max_length=64)
    automation_identifier = serializers.CharField(required=False, allow_blank=True, max_length=128)
    automation_script = serializers.CharField(required=False, allow_blank=True)

    def validate_steps(self, value):
        return normalize_steps(value)


class TestCaseMoveSerializer(serializers.Serializer):
    module_id = serializers.IntegerField(required=False, allow_null=True)


class TestCaseBatchSerializer(serializers.Serializer):
    op = serializers.ChoiceField(choices=["update", "move", "tag", "delete", "restore"])
    test_case_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    params = serializers.DictField(required=False)


class TestCaseListSerializer(serializers.ModelSerializer):
    module_name = serializers.CharField(source="module.name", read_only=True, default=None)
    owner = UserBriefSerializer(read_only=True)
    tags = TagBriefSerializer(many=True, read_only=True)
    precondition_summary = serializers.SerializerMethodField()
    created_at = IsoDateTimeField(read_only=True)
    updated_at = IsoDateTimeField(read_only=True)

    class Meta:
        model = TestCase
        fields = [
            "id", "case_key", "title", "priority", "case_type", "status",
            "module_id", "module_name", "owner", "tags", "automation_status",
            "current_version", "precondition_summary", "created_at", "updated_at",
        ]

    def get_precondition_summary(self, obj):
        text = obj.precondition or ""
        return text if len(text) <= 200 else text[:200]


class TestCaseDetailSerializer(serializers.ModelSerializer):
    module_id = serializers.IntegerField(read_only=True)
    module_name = serializers.CharField(source="module.name", read_only=True, default=None)
    module_path = serializers.SerializerMethodField()
    owner = UserBriefSerializer(read_only=True)
    creator = UserBriefSerializer(read_only=True)
    tags = TagBriefSerializer(many=True, read_only=True)
    steps = serializers.SerializerMethodField()
    expected_result = serializers.SerializerMethodField()
    change_summary = serializers.SerializerMethodField()
    created_at = IsoDateTimeField(read_only=True)
    updated_at = IsoDateTimeField(read_only=True)

    class Meta:
        model = TestCase
        fields = [
            "id", "case_key", "title", "description", "precondition",
            "priority", "case_type", "status",
            "automation_status", "automation_framework", "automation_identifier", "automation_script",
            "module_id", "module_name", "module_path", "owner", "creator", "tags",
            "steps", "expected_result", "change_summary", "current_version",
            "sort_order", "created_at", "updated_at",
        ]

    def get_module_path(self, obj):
        chain = []
        module = obj.module
        while module is not None:
            chain.append({"id": module.id, "name": module.name})
            module = module.parent
        chain.reverse()
        return chain

    def get_steps(self, obj):
        return self.context["version"].steps

    def get_expected_result(self, obj):
        return self.context["version"].expected_result

    def get_change_summary(self, obj):
        return self.context["version"].change_summary


class TestCaseVersionListSerializer(serializers.ModelSerializer):
    created_by = UserBriefSerializer(read_only=True)
    created_at = IsoDateTimeField(read_only=True)

    class Meta:
        model = TestCaseVersion
        fields = ["id", "version", "title", "change_summary", "created_by", "created_at"]


class TestCaseVersionDetailSerializer(serializers.ModelSerializer):
    created_by = UserBriefSerializer(read_only=True)
    created_at = IsoDateTimeField(read_only=True)

    class Meta:
        model = TestCaseVersion
        fields = [
            "id", "test_case", "version", "title", "description", "precondition",
            "steps", "expected_result", "change_summary", "created_by", "created_at",
        ]


class MappingJSONField(serializers.JSONField):
    """导入字段映射：multipart 上传时以 JSON 字符串传递，这里统一解析成对象。"""

    def to_internal_value(self, data):
        if isinstance(data, str):
            if not data.strip():
                return {}
            try:
                data = json.loads(data)
            except ValueError:
                raise serializers.ValidationError("mapping 必须是合法的 JSON 对象")
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise serializers.ValidationError("mapping 必须是 JSON 对象")
        return data


class TestCaseImportSerializer(serializers.Serializer):
    """导入请求（§61）：xlsx/csv 文件 + 可选字段映射 + 是否预览（dry_run 默认不落库）。"""

    file = serializers.FileField()
    mapping = MappingJSONField(required=False)
    dry_run = serializers.BooleanField(required=False, default=True)

    def validate_file(self, value):
        name = value.name or ""
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if extension not in {"csv", "xlsx"}:
            raise serializers.ValidationError("仅支持 CSV 或 XLSX 格式的文件")
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("文件大小不能超过 10MB")
        return value
