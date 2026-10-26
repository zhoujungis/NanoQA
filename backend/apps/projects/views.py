"""项目 API：项目 / 成员 / 模块树 / 标签。"""
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects import serializers
from apps.projects.models import Module, ProjectMember, Tag
from apps.projects.services import members as member_service
from apps.projects.services import modules as module_service
from apps.projects.services import projects as project_service
from apps.projects.services import tags as tag_service
from common.exceptions import NanoAPIError, NotFoundError
from common.permissions import HasProjectPermission


class MethodPermissionMixin:
    """按 HTTP 方法映射权限码；由 HasProjectPermission 读取 view.permission_codename。"""

    method_permissions: dict = {}

    @property
    def permission_codename(self):
        return self.method_permissions.get(getattr(self.request, "method", ""))


class ProjectListCreateView(generics.ListCreateAPIView):
    """GET /projects/ 可见项目列表（分页，?q=、?status=）；POST 创建项目（project.create，组织内）。"""

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.ProjectSerializer

    def get_queryset(self):
        return project_service.list_projects(
            self.request.user,
            q=self.request.query_params.get("q"),
            status=self.request.query_params.get("status"),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data["organization_id"] = request.data.get("organization_id")
        project = project_service.create_project(request.user, data, request=request)
        return Response(self.get_serializer(project).data, status=201)


class ProjectDetailView(MethodPermissionMixin, APIView):
    """GET/PATCH/DELETE /projects/{id}/（project.read/update/delete）。"""

    permission_classes = [IsAuthenticated, HasProjectPermission]
    method_permissions = {
        "GET": "project.read",
        "PATCH": "project.update",
        "DELETE": "project.delete",
    }

    def get(self, request, project_id):
        project = project_service.get_project(project_id)
        return Response(serializers.ProjectSerializer(project, context={"request": request}).data)

    def patch(self, request, project_id):
        project = project_service.get_project(project_id)
        serializer = serializers.ProjectSerializer(
            project, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        project = project_service.update_project(
            project, serializer.validated_data,
            request.data.get("updated_at"), request=request,
        )
        return Response(serializers.ProjectSerializer(project, context={"request": request}).data)

    def delete(self, request, project_id):
        project = project_service.get_project(project_id)
        project = project_service.archive_project(project, request=request)
        return Response({"archived": True, "status": project.status})


class ProjectMemberListCreateView(APIView):
    """GET/POST /projects/{id}/members/（user.manage）。"""

    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "user.manage"

    def get(self, request, project_id):
        project = project_service.get_project(project_id)
        members = project.members.select_related("user", "role").order_by("id")
        return Response(serializers.ProjectMemberSerializer(members, many=True).data)

    def post(self, request, project_id):
        project = project_service.get_project(project_id)
        serializer = serializers.ProjectMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = member_service.add_project_member(
            project,
            serializer.validated_data["user_id"],
            serializer.validated_data["role_id"],
            request=request,
        )
        return Response(serializers.ProjectMemberSerializer(member).data, status=201)


class ProjectMemberDetailView(APIView):
    """PATCH/DELETE /projects/members/{id}/（user.manage）。"""

    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "user.manage"

    def get_project(self, request):
        member = member_service.get_project_member(self.kwargs["member_id"])
        return member.project

    def patch(self, request, member_id):
        member = member_service.get_project_member(member_id)
        serializer = serializers.ProjectMemberSerializer(
            member, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        if "role_id" not in serializer.validated_data:
            raise NanoAPIError("缺少 role_id")
        member = member_service.update_project_member(
            member, serializer.validated_data["role_id"], request=request
        )
        return Response(serializers.ProjectMemberSerializer(member).data)

    def delete(self, request, member_id):
        member = member_service.get_project_member(member_id)
        member_service.remove_project_member(member, request=request)
        return Response({"deleted": True})


class ModuleTreeCreateView(MethodPermissionMixin, APIView):
    """GET/POST /projects/{id}/modules/（testcase.read / testcase.create）。"""

    permission_classes = [IsAuthenticated, HasProjectPermission]
    method_permissions = {"GET": "testcase.read", "POST": "testcase.create"}

    def get(self, request, project_id):
        project = project_service.get_project(project_id)
        return Response(module_service.module_tree(project))

    def post(self, request, project_id):
        project = project_service.get_project(project_id)
        serializer = serializers.ModuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        module = module_service.create_module(
            project, serializer.validated_data, request=request
        )
        return Response(serializers.ModuleSerializer(module).data, status=201)


class ModuleDetailView(MethodPermissionMixin, APIView):
    """PATCH/DELETE /modules/{id}/（testcase.update / testcase.delete）。"""

    permission_classes = [IsAuthenticated, HasProjectPermission]
    method_permissions = {"PATCH": "testcase.update", "DELETE": "testcase.delete"}

    def get_module(self):
        module = Module.objects.filter(pk=self.kwargs["module_id"]).select_related("project", "parent").first()
        if module is None:
            raise NotFoundError("模块不存在")
        return module

    def get_project(self, request):
        return self.get_module().project

    def patch(self, request, module_id):
        module = self.get_module()
        serializer = serializers.ModuleSerializer(module, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        module = module_service.update_module(
            module, serializer.validated_data,
            request.data.get("updated_at"), request=request,
        )
        return Response(serializers.ModuleSerializer(module).data)

    def delete(self, request, module_id):
        module = self.get_module()
        module_service.delete_module(module, request=request)
        return Response({"deleted": True})


class ModuleMoveView(APIView):
    """POST /modules/{id}/move/（testcase.update）：body {parent_id, sort_order}。"""

    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "testcase.update"

    def get_project(self, request):
        module = Module.objects.filter(pk=self.kwargs["module_id"]).first()
        if module is None:
            raise NotFoundError("模块不存在")
        return module.project

    def post(self, request, module_id):
        module = Module.objects.filter(pk=module_id).select_related("project", "parent").first()
        if module is None:
            raise NotFoundError("模块不存在")
        data = request.data if isinstance(request.data, dict) else {}
        if "parent_id" not in data and "sort_order" not in data:
            raise NanoAPIError("缺少 parent_id 或 sort_order")
        module = module_service.move_module(
            module,
            data.get("parent_id"),
            data.get("sort_order"),
            request=request,
        )
        return Response(serializers.ModuleSerializer(module).data)


class TagListCreateView(MethodPermissionMixin, APIView):
    """GET/POST /projects/{id}/tags/（testcase.read / testcase.create）。"""

    permission_classes = [IsAuthenticated, HasProjectPermission]
    method_permissions = {"GET": "testcase.read", "POST": "testcase.create"}

    def get(self, request, project_id):
        project = project_service.get_project(project_id)
        return Response(serializers.TagSerializer(project.tags.order_by("id"), many=True).data)

    def post(self, request, project_id):
        project = project_service.get_project(project_id)
        serializer = serializers.TagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tag = tag_service.create_tag(project, serializer.validated_data, request=request)
        return Response(serializers.TagSerializer(tag).data, status=201)


class TagDetailView(MethodPermissionMixin, APIView):
    """PATCH/DELETE /tags/{id}/（testcase.update / testcase.delete）。"""

    permission_classes = [IsAuthenticated, HasProjectPermission]
    method_permissions = {"PATCH": "testcase.update", "DELETE": "testcase.delete"}

    def get_tag(self):
        tag = Tag.objects.filter(pk=self.kwargs["tag_id"]).select_related("project").first()
        if tag is None:
            raise NotFoundError("标签不存在")
        return tag

    def get_project(self, request):
        return self.get_tag().project

    def patch(self, request, tag_id):
        tag = self.get_tag()
        serializer = serializers.TagSerializer(tag, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        tag = tag_service.update_tag(tag, serializer.validated_data, request=request)
        return Response(serializers.TagSerializer(tag).data)

    def delete(self, request, tag_id):
        tag = self.get_tag()
        tag_service.remove_tag(tag, request=request)
        return Response({"deleted": True})
