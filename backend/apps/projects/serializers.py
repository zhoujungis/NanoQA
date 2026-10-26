"""项目域序列化器：Project / ProjectMember / Module / Tag。"""
from rest_framework import serializers

from apps.accounts.serializers import RoleSerializer, UserSerializer
from apps.projects.models import KEY_VALIDATOR, Module, Project, ProjectMember, Tag


class ProjectSerializer(serializers.ModelSerializer):
    key = serializers.CharField(max_length=16, validators=[KEY_VALIDATOR])
    role = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id", "organization", "name", "key", "description", "status",
            "owner", "role", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "organization", "owner", "role", "created_at", "updated_at"]

    def get_role(self, obj):
        """当前用户在该项目的角色 code（项目成员视角）。"""
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return None
        memberships = getattr(obj, "_my_memberships", None)
        if memberships is None:
            memberships = list(obj.members.filter(user=request.user).select_related("role")[:1])
        return memberships[0].role.code if memberships else None


class ProjectMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True)
    role_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = ProjectMember
        fields = ["id", "user", "role", "user_id", "role_id", "created_at"]
        read_only_fields = ["id", "created_at"]


class ModuleSerializer(serializers.ModelSerializer):
    parent_id = serializers.PrimaryKeyRelatedField(
        source="parent", queryset=Module.objects.all(),
        required=False, allow_null=True,
    )

    class Meta:
        model = Module
        fields = ["id", "name", "description", "parent_id", "sort_order", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "color"]
        read_only_fields = ["id"]
