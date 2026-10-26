"""项目服务：创建（含默认组织兜底）、更新（乐观锁）、归档软删、可见列表。"""
from django.db import transaction
from django.db.models import Prefetch, Q

from apps.accounts.models import Role
from apps.accounts.services.permissions import (
    global_permissions_for_user,
    has_organization_permission,
)
from apps.audit.services import AuditService
from apps.organizations.models import Organization, OrganizationMember
from apps.projects.models import Project, ProjectMember
from common.exceptions import (
    BusinessConflictError,
    NanoAPIError,
    NotFoundError,
    PermissionDeniedError,
)
from common.optimistic import save_with_lock
from common.utils import model_diff, model_snapshot

PROJECT_FIELDS = ["name", "key", "description", "status"]
EDITABLE_FIELDS = ["name", "description", "status"]


def get_default_organization(user, request=None) -> Organization:
    """取/建用户默认组织（slug=user-{id}，owner=用户并绑定 admin 角色）。"""
    slug = f"user-{user.id}"
    existing = Organization.objects.filter(slug=slug).first()
    if existing is not None:
        return existing
    admin_role = Role.objects.get(code="admin")
    with transaction.atomic():
        org = Organization.objects.create(
            name=user.display_name or user.username, slug=slug, owner=user
        )
        OrganizationMember.objects.get_or_create(
            organization=org, user=user, defaults={"role": admin_role}
        )
        AuditService.record(
            "create", org, request=request,
            new_data={"name": org.name, "slug": slug},
        )
    return org


def resolve_create_organization(user, organization_id, request=None) -> Organization:
    """解析建项目的目标组织并判定 project.create。"""
    if organization_id:
        org = Organization.objects.filter(pk=organization_id).first()
        if org is None:
            raise NotFoundError("组织不存在")
        if not has_organization_permission(user, org, "project.create"):
            raise PermissionDeniedError("权限不足: project.create")
        return org
    if "project.create" not in global_permissions_for_user(user):
        raise PermissionDeniedError("权限不足: project.create")
    return get_default_organization(user, request=request)


def create_project(user, data: dict, request=None) -> Project:
    org = resolve_create_organization(user, data.get("organization_id"), request=request)
    key = data["key"]
    if Project.objects.filter(organization=org, key=key).exists():
        raise BusinessConflictError("项目 Key 在该组织内已存在")
    admin_role = Role.objects.get(code="admin")
    with transaction.atomic():
        project = Project.objects.create(
            organization=org,
            name=data["name"],
            key=key,
            description=data.get("description", ""),
            status=data.get("status", Project.STATUS_ACTIVE),
            owner=user,
        )
        ProjectMember.objects.create(project=project, user=user, role=admin_role)
        AuditService.record(
            "create", project, request=request,
            new_data=model_snapshot(project, fields=PROJECT_FIELDS),
        )
    return project


def list_projects(user, q: str | None = None, status: str | None = None):
    """当前用户可见项目（ProjectMember 关联；系统管理员看全部）。"""
    queryset = Project.objects.all().select_related("organization", "owner")
    if not (user.is_superuser or user.is_system_admin):
        queryset = queryset.filter(members__user=user)
    queryset = queryset.distinct()
    if q:
        queryset = queryset.filter(Q(name__icontains=q) | Q(key__icontains=q))
    if status:
        queryset = queryset.filter(status=status)
    return queryset.prefetch_related(
        Prefetch(
            "members",
            queryset=ProjectMember.objects.filter(user=user).select_related("role"),
            to_attr="_my_memberships",
        )
    )


def get_project(project_id) -> Project:
    project = Project.objects.filter(pk=project_id).select_related("organization", "owner").first()
    if project is None:
        raise NotFoundError("项目不存在")
    return project


def update_project(project: Project, data: dict, expected_updated_at, request=None) -> Project:
    if "key" in data and data["key"] != project.key:
        raise NanoAPIError("项目 Key 创建后不可修改")
    old_data = model_snapshot(project, fields=PROJECT_FIELDS)
    for field in EDITABLE_FIELDS:
        if field in data:
            setattr(project, field, data[field])
    update_fields = [f for f in EDITABLE_FIELDS if f in data] or ["name"]
    with transaction.atomic():
        save_with_lock(project, expected_updated_at, update_fields)
        new_data = model_snapshot(project, fields=PROJECT_FIELDS)
        diff_old, diff_new = model_diff(old_data, new_data)
        AuditService.record("update", project, request=request, old_data=diff_old, new_data=diff_new)
    return project


def archive_project(project: Project, request=None) -> Project:
    """DELETE 软删语义：status→archived + 审计，不物理删除。"""
    if project.status == Project.STATUS_ARCHIVED:
        return project
    old_data = model_snapshot(project, fields=["status"])
    project.status = Project.STATUS_ARCHIVED
    with transaction.atomic():
        project.save(update_fields=["status", "updated_at"])
        AuditService.record(
            "delete", project, request=request,
            old_data=old_data, new_data={"status": Project.STATUS_ARCHIVED},
        )
    return project
