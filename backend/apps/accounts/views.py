"""认证与账号视图。"""
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import serializers
from apps.accounts.models import Role
from apps.accounts.services import auth as auth_service
from apps.accounts.services import roles as role_service
from apps.accounts.services import users as user_service
from apps.accounts.services.permissions import global_permissions_for_user
from common.permissions import PERMISSION_CODENAMES


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = serializers.LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, tokens = auth_service.login(
            serializer.validated_data["email"], serializer.validated_data["password"]
        )
        return Response({**tokens, "user": serializers.UserSerializer(user).data})


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"detail": "缺少 refresh"})
        try:
            token = RefreshToken(refresh)
        except Exception:
            return Response(status=status.HTTP_401_UNAUTHORIZED, data={"detail": "无效的刷新令牌"})
        return Response({"access": str(token.access_token), "refresh": str(token)})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        auth_service.logout(request.data.get("refresh", ""))
        return Response({"logged_out": True})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        memberships = []
        for membership in user.project_memberships.select_related("project", "role"):
            memberships.append({
                "project_id": membership.project_id,
                "project_key": membership.project.key,
                "project_name": membership.project.name,
                "role": membership.role.code,
                "role_name": membership.role.name,
            })
        permissions = sorted(
            set(
                user.project_memberships.values_list("role__permissions__codename", flat=True)
            ) - {None}
        )
        if user.is_superuser or user.is_system_admin:
            permissions = list(PERMISSION_CODENAMES)
        return Response({
            "user": serializers.UserSerializer(user).data,
            "memberships": memberships,
            "permissions": permissions,
            "is_system_admin": bool(user.is_superuser or user.is_system_admin),
        })


class HasGlobalPermission(BasePermission):
    """全局（非项目上下文）权限判定：按 view.permission_codename 校验用户全部角色权限并集。"""

    message = "权限不足"

    def has_permission(self, request, view):
        codename = getattr(view, "permission_codename", None)
        if not codename or request.method in ("OPTIONS", "HEAD"):
            return bool(request.user and request.user.is_authenticated)
        if codename not in global_permissions_for_user(request.user):
            self.message = f"权限不足: {codename}"
            return False
        return True


class UserListView(generics.ListAPIView):
    """GET /api/v1/users/ 用户列表（user.manage）。"""

    serializer_class = serializers.UserSerializer
    permission_classes = [IsAuthenticated, HasGlobalPermission]
    permission_codename = "user.manage"

    def get_queryset(self):
        return user_service.search_users(self.request.query_params.get("q"))


class RoleListCreateView(generics.ListCreateAPIView):
    """GET /api/v1/roles/（认证即可）；POST 创建自定义角色（role.manage）。"""

    queryset = Role.objects.all().prefetch_related("permissions")
    serializer_class = serializers.RoleSerializer
    pagination_class = None  # 小型引用列表：返回完整数组
    http_method_names = ["get", "post", "head", "options"]
    permission_codename = "role.manage"

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), HasGlobalPermission()]

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = role_service.create_role(
            code=data["code"],
            name=data["name"],
            organization=data.get("organization"),
            permission_codenames=[
                p.codename for p in data.get("permissions", [])
            ],
            request=self.request,
        )


class RoleDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/roles/{id}/；PATCH 支持乐观锁（回传 updated_at），系统角色禁改权限。"""

    queryset = Role.objects.all().prefetch_related("permissions")
    serializer_class = serializers.RoleSerializer
    lookup_url_kwarg = "role_id"
    http_method_names = ["get", "patch", "head", "options"]
    permission_codename = "role.manage"

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), HasGlobalPermission()]

    def perform_update(self, serializer):
        role_service.update_role(
            serializer.instance,
            serializer.validated_data,
            self.request.data.get("updated_at"),
            request=self.request,
        )
        serializer.instance.refresh_from_db()
