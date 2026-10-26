"""组织序列化器。"""
from rest_framework import serializers

from apps.accounts.serializers import RoleSerializer, UserSerializer
from apps.organizations.models import Organization, OrganizationMember


class OrganizationSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(max_length=64, required=False)

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "owner", "created_at", "updated_at"]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]


class OrganizationMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True)
    role_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = OrganizationMember
        fields = ["id", "user", "role", "user_id", "role_id", "created_at"]
        read_only_fields = ["id", "created_at"]
