"""账号序列化器。"""
from rest_framework import serializers

from apps.accounts.models import Permission, Role, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "display_name", "avatar", "is_active", "date_joined"]
        read_only_fields = fields


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "codename", "name", "group"]


class RoleSerializer(serializers.ModelSerializer):
    permission_codenames = serializers.SlugRelatedField(
        slug_field="codename", queryset=Permission.objects.all(), many=True,
        source="permissions", required=False,
    )

    class Meta:
        model = Role
        fields = ["id", "code", "name", "is_system", "organization", "permission_codenames", "updated_at"]
        read_only_fields = ["id", "is_system", "updated_at"]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
