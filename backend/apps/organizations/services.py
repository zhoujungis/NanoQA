"""组织服务：组织创建 / 更新 / 成员绑定（§9.2）。"""
import re

from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify

from apps.accounts.models import Role, User
from apps.accounts.services.permissions import has_organization_permission
from apps.audit.services import AuditService
from apps.organizations.models import Organization, OrganizationMember
from common.exceptions import BusinessConflictError, NanoAPIError, NotFoundError, PermissionDeniedError
from common.optimistic import save_with_lock
from common.utils import model_diff, model_snapshot

SLUG_RE = re.compile(r"^[-a-zA-Z0-9_]+$")
ORG_FIELDS = ["name", "slug"]


# ---------------------------------------------------------------- 组织
def ensure_unique_slug(name: str, provided: str | None = None) -> str:
    """slug 唯一：提供则校验，未提供则由 name 生成。"""
    if provided:
        slug = provided.strip()
        if not SLUG_RE.match(slug):
            raise NanoAPIError("组织标识（slug）只能包含字母、数字、连字符或下划线")
        if Organization.objects.filter(slug=slug).exists():
            raise BusinessConflictError("组织标识（slug）已存在")
        return slug
    base = slugify(name)[:48].strip("-") or "org"
    slug, index = base, 2
    while Organization.objects.filter(slug=slug).exists():
        slug = f"{base}-{index}"
        index += 1
    return slug


def create_organization(user, data: dict, request=None) -> Organization:
    name = (data.get("name") or "").strip()
    slug = ensure_unique_slug(name, data.get("slug"))
    admin_role = Role.objects.get(code="admin")
    with transaction.atomic():
        org = Organization.objects.create(name=name, slug=slug, owner=user)
        OrganizationMember.objects.create(organization=org, user=user, role=admin_role)
        AuditService.record(
            "create", org, request=request, new_data={"name": name, "slug": slug},
        )
    return org


def list_organizations(user):
    """当前用户所属组织（系统管理员可见全部）。"""
    queryset = Organization.objects.all()
    if user.is_superuser or user.is_system_admin:
        return queryset.order_by("id")
    return queryset.filter(Q(members__user=user) | Q(owner=user)).distinct().order_by("id")


def get_organization(organization_id) -> Organization:
    org = Organization.objects.filter(pk=organization_id).first()
    if org is None:
        raise NotFoundError("组织不存在")
    return org


def require_org_access(user, org: Organization):
    """组织可见性：成员 / owner / 系统管理员。"""
    if user.is_superuser or user.is_system_admin or org.owner_id == user.pk:
        return
    if not OrganizationMember.objects.filter(organization=org, user=user).exists():
        raise PermissionDeniedError("无权访问该组织")


def require_org_manage(user, org: Organization, codename: str = "user.manage"):
    if not has_organization_permission(user, org, codename):
        raise PermissionDeniedError(f"权限不足: {codename}")


def update_organization(org: Organization, data: dict, expected_updated_at, request=None) -> Organization:
    old_data = model_snapshot(org, fields=ORG_FIELDS)
    if "slug" in data and data["slug"] != org.slug:
        if Organization.objects.filter(slug=data["slug"]).exclude(pk=org.pk).exists():
            raise BusinessConflictError("组织标识（slug）已存在")
    for field in ORG_FIELDS:
        if field in data:
            setattr(org, field, data[field])
    with transaction.atomic():
        save_with_lock(org, expected_updated_at, [f for f in ORG_FIELDS if f in data] or ["name"])
        new_data = model_snapshot(org, fields=ORG_FIELDS)
        diff_old, diff_new = model_diff(old_data, new_data)
        AuditService.record("update", org, request=request, old_data=diff_old, new_data=diff_new)
    return org


# ---------------------------------------------------------------- 成员
def _check_role_scope(role: Role, org: Organization):
    if role.organization_id not in (None, org.pk):
        raise BusinessConflictError("角色不属于该组织")


def get_organization_member(member_id) -> OrganizationMember:
    member = OrganizationMember.objects.filter(pk=member_id).select_related("organization", "user", "role").first()
    if member is None:
        raise NotFoundError("组织成员记录不存在")
    return member


def add_organization_member(org: Organization, user_id, role_id, request=None) -> OrganizationMember:
    member_user = User.objects.filter(pk=user_id).first()
    if member_user is None:
        raise NotFoundError("用户不存在")
    role = Role.objects.filter(pk=role_id).first()
    if role is None:
        raise NotFoundError("角色不存在")
    _check_role_scope(role, org)
    if OrganizationMember.objects.filter(organization=org, user=member_user).exists():
        raise BusinessConflictError("该用户已是组织成员")
    with transaction.atomic():
        member = OrganizationMember.objects.create(organization=org, user=member_user, role=role)
        AuditService.record(
            "link", member, request=request, organization=org,
            object_ref=f"org{org.pk}:user{member_user.pk}",
            new_data={"user_id": member_user.pk, "role_id": role.pk, "role_code": role.code},
        )
    return member


def update_organization_member(member: OrganizationMember, role_id, request=None) -> OrganizationMember:
    role = Role.objects.filter(pk=role_id).first()
    if role is None:
        raise NotFoundError("角色不存在")
    _check_role_scope(role, member.organization)
    old_role = member.role
    if role.pk == old_role.pk:
        return member
    with transaction.atomic():
        member.role = role
        member.save(update_fields=["role"])
        AuditService.record(
            "update", member, request=request, organization=member.organization,
            object_ref=f"org{member.organization_id}:user{member.user_id}",
            old_data={"role_id": old_role.pk, "role_code": old_role.code},
            new_data={"role_id": role.pk, "role_code": role.code},
        )
    return member


def remove_organization_member(member: OrganizationMember, request=None):
    with transaction.atomic():
        AuditService.record(
            "unlink", member, request=request, organization=member.organization,
            object_ref=f"org{member.organization_id}:user{member.user_id}",
            old_data={"user_id": member.user_id, "role_id": member.role_id, "role_code": member.role.code},
        )
        member.delete()
