"""RBAC 权限（§4）：后端最终判定，前端仅做展示层。"""
from django.conf import settings
from rest_framework.permissions import BasePermission

from common.exceptions import CODE_NOT_FOUND, CODE_PERMISSION_DENIED, NotFoundError

# §4 权限粒度全集（种子数据来源）
PERMISSION_CODENAMES = [
    "project.read", "project.create", "project.update", "project.delete",
    "requirement.read", "requirement.create", "requirement.update", "requirement.delete",
    "testcase.read", "testcase.create", "testcase.update", "testcase.delete",
    "testcase.execute", "testcase.review",
    "testplan.read", "testplan.create", "testplan.update", "testplan.delete", "testplan.execute",
    "defect.read", "defect.create", "defect.update", "defect.delete",
    "report.read",
    "user.manage", "role.manage", "audit.read",
]


def resolve_project(request, view):
    """解析当前请求所属项目，结果缓存在 request._nano_project。"""
    cached = getattr(request, "_nano_project", None)
    if cached is not None:
        return cached

    from apps.projects.models import Project

    project = None
    project_pk = view.kwargs.get("project_id") or view.kwargs.get("project_pk")
    if project_pk:
        try:
            project = Project.objects.get(pk=project_pk)
        except Project.DoesNotExist:
            raise NotFoundError("项目不存在", code=CODE_NOT_FOUND)
    elif hasattr(view, "get_project"):
        project = view.get_project(request)
    else:
        obj = getattr(request, "_nano_obj", None)
        if obj is None and hasattr(view, "get_cached_object"):
            obj = view.get_cached_object()
            request._nano_obj = obj
        if obj is not None:
            project = getattr(obj, "project", None)

    if project is None:
        raise NotFoundError("无法解析项目上下文", code=CODE_NOT_FOUND)
    request._nano_project = project
    return project


def get_user_permissions(user, project) -> set[str]:
    """用户在某项目下的权限集合（系统管理员拥有全部）。"""
    if not user or not user.is_authenticated:
        return set()
    if getattr(user, "is_superuser", False) or getattr(user, "is_system_admin", False):
        return set(PERMISSION_CODENAMES)
    from apps.accounts.services.permissions import permissions_for_user
    return permissions_for_user(user, project)


def has_project_permission(user, project, codename: str) -> bool:
    if not codename:
        return True
    return codename in get_user_permissions(user, project)


class HasProjectPermission(BasePermission):
    """按 view.permission_codename 判定项目级权限。

    用法：视图设置 `permission_codename = "testcase.update"`；
    对象型视图可设置 `project_fk_path = "project"` 或实现 `get_project()`。
    """

    message = "权限不足"

    def has_permission(self, request, view):
        codename = getattr(view, "permission_codename", None)
        if not codename or request.method in ("OPTIONS", "HEAD"):
            return bool(request.user and request.user.is_authenticated)
        project = resolve_project(request, view)
        if not has_project_permission(request.user, project, codename):
            self.message = f"权限不足: {codename}"
            return False
        return True


class IsSystemAdmin(BasePermission):
    message = "需要系统管理员权限"

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and (user.is_superuser or getattr(user, "is_system_admin", False))
        )
