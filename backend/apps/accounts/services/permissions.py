"""权限解析：用户在项目 / 组织下的权限集合。"""
from common.permissions import PERMISSION_CODENAMES


def _role_permissions(role_ids) -> set[str]:
    if not role_ids:
        return set()
    from apps.accounts.models import Role

    perms = set(
        Role.objects.filter(id__in=role_ids)
        .values_list("permissions__codename", flat=True)
        .distinct()
    )
    perms.discard(None)
    return perms


def global_permissions_for_user(user) -> set[str]:
    """用户全局权限并集 = 全部项目角色 ∪ 全部组织角色（系统管理员拥有全部）。"""
    if not user or not user.is_authenticated:
        return set()
    if user.is_superuser or user.is_system_admin:
        return set(PERMISSION_CODENAMES)
    role_ids: set[int] = set()
    role_ids.update(user.project_memberships.values_list("role_id", flat=True))
    role_ids.update(user.org_memberships.values_list("role_id", flat=True))
    return _role_permissions(role_ids)


def has_global_permission(user, codename: str) -> bool:
    return bool(codename) and codename in global_permissions_for_user(user)


def permissions_for_organization(user, organization) -> set[str]:
    """用户在组织下的权限 = 组织角色 ∪ 该组织内项目角色；组织 owner / 系统管理员拥有全部。"""
    if not user or not user.is_authenticated or organization is None:
        return set()
    if user.is_superuser or user.is_system_admin:
        return set(PERMISSION_CODENAMES)
    if organization.owner_id == user.pk:
        return set(PERMISSION_CODENAMES)
    role_ids: set[int] = set()
    role_ids.update(
        organization.members.filter(user=user).values_list("role_id", flat=True)
    )
    role_ids.update(
        user.project_memberships.filter(project__organization=organization)
        .values_list("role_id", flat=True)
    )
    return _role_permissions(role_ids)


def has_organization_permission(user, organization, codename: str) -> bool:
    return bool(codename) and codename in permissions_for_organization(user, organization)


def permissions_for_user(user, project) -> set[str]:
    """用户在项目下的权限 = 项目角色权限 ∪ 组织角色权限。

    v0.1 不做缓存：成员/角色变更需要即时生效（无失效机制的缓存会造成 60s 权限滞后）。
    """
    if not user or not user.is_authenticated:
        return set()
    if user.is_superuser or user.is_system_admin:
        return set(PERMISSION_CODENAMES)

    role_ids: set[int] = set()
    if project is not None:
        role_ids.update(
            project.members.filter(user=user).values_list("role_id", flat=True)
        )
        role_ids.update(
            project.organization.members.filter(user=user).values_list("role_id", flat=True)
        )
    return _role_permissions(role_ids)


def role_for_user(user, project):
    """取用户在项目中的主角色（用于 /auth/me 返回）。"""
    if project is None:
        return None
    membership = project.members.filter(user=user).select_related("role").first()
    return membership.role if membership else None
