"""组织 API：组织 CRUD 与成员绑定。"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations import serializers
from apps.organizations.services import (
    add_organization_member,
    create_organization,
    get_organization,
    get_organization_member,
    list_organizations,
    remove_organization_member,
    require_org_access,
    require_org_manage,
    update_organization,
    update_organization_member,
)
from common.exceptions import NanoAPIError


class OrganizationListCreateView(APIView):
    """GET 当前用户所属组织；POST 创建组织（创建者为 owner + admin 角色）。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = list_organizations(request.user)
        return Response(serializers.OrganizationSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = serializers.OrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = create_organization(
            request.user, serializer.validated_data, request=request
        )
        return Response(serializers.OrganizationSerializer(org).data, status=201)


class OrganizationDetailView(APIView):
    """GET/PATCH /organizations/{id}/；PATCH 走乐观锁（回传 updated_at）。"""

    permission_classes = [IsAuthenticated]

    def get(self, request, organization_id):
        org = get_organization(organization_id)
        require_org_access(request.user, org)
        return Response(serializers.OrganizationSerializer(org).data)

    def patch(self, request, organization_id):
        org = get_organization(organization_id)
        require_org_manage(request.user, org, "user.manage")
        serializer = serializers.OrganizationSerializer(org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        org = update_organization(
            org, serializer.validated_data,
            request.data.get("updated_at"), request=request,
        )
        return Response(serializers.OrganizationSerializer(org).data)


class OrganizationMemberListCreateView(APIView):
    """GET/POST /organizations/{id}/members/（user.manage）。"""

    permission_classes = [IsAuthenticated]

    def get(self, request, organization_id):
        org = get_organization(organization_id)
        require_org_manage(request.user, org, "user.manage")
        members = org.members.select_related("user", "role", "role__organization").order_by("id")
        return Response(serializers.OrganizationMemberSerializer(members, many=True).data)

    def post(self, request, organization_id):
        org = get_organization(organization_id)
        require_org_manage(request.user, org, "user.manage")
        serializer = serializers.OrganizationMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = add_organization_member(
            org,
            serializer.validated_data["user_id"],
            serializer.validated_data["role_id"],
            request=request,
        )
        return Response(serializers.OrganizationMemberSerializer(member).data, status=201)


class OrganizationMemberDetailView(APIView):
    """PATCH/DELETE /organizations/members/{id}/（user.manage）。"""

    permission_classes = [IsAuthenticated]

    def patch(self, request, member_id):
        member = get_organization_member(member_id)
        require_org_manage(request.user, member.organization, "user.manage")
        serializer = serializers.OrganizationMemberSerializer(
            member, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        if "role_id" not in serializer.validated_data:
            raise NanoAPIError("缺少 role_id")
        member = update_organization_member(
            member, serializer.validated_data["role_id"], request=request
        )
        return Response(serializers.OrganizationMemberSerializer(member).data)

    def delete(self, request, member_id):
        member = get_organization_member(member_id)
        require_org_manage(request.user, member.organization, "user.manage")
        remove_organization_member(member, request=request)
        return Response({"deleted": True})
