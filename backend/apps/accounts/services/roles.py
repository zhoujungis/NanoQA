"""角色服务：自定义角色创建 / 修改（系统角色禁止改权限）。"""
from django.db import transaction

from apps.accounts.models import Role
from apps.audit.services import AuditService
from common.exceptions import BusinessConflictError
from common.optimistic import save_with_lock
from common.utils import model_diff, model_snapshot

SCALAR_FIELDS = ["code", "name", "organization"]


def _permission_codenames(role: Role) -> list[str]:
    return sorted(role.permissions.values_list("codename", flat=True))


def create_role(*, code: str, name: str, organization=None, permission_codenames=(), request=None) -> Role:
    from apps.accounts.models import Permission

    permissions = list(Permission.objects.filter(codename__in=permission_codenames))
    with transaction.atomic():
        role = Role.objects.create(
            code=code, name=name, is_system=False, organization=organization
        )
        role.permissions.set(permissions)
        AuditService.record(
            "create", role, request=request,
            new_data={"code": code, "name": name, "permission_codenames": _permission_codenames(role)},
        )
    return role


def update_role(role: Role, data: dict, expected_updated_at, request=None) -> Role:
    old_data = model_snapshot(role, fields=SCALAR_FIELDS)
    old_codenames = _permission_codenames(role)

    if "permissions" in data and role.is_system:
        raise BusinessConflictError("系统内置角色禁止修改权限")

    for field in SCALAR_FIELDS:
        if field in data:
            setattr(role, field, data[field])

    with transaction.atomic():
        save_with_lock(role, expected_updated_at, [f for f in SCALAR_FIELDS if f in data] or ["name"])
        if "permissions" in data:
            role.permissions.set(data["permissions"])
        new_data = model_snapshot(role, fields=SCALAR_FIELDS)
        diff_old, diff_new = model_diff(old_data, new_data)
        new_codenames = _permission_codenames(role)
        if new_codenames != old_codenames:
            diff_old["permission_codenames"] = old_codenames
            diff_new["permission_codenames"] = new_codenames
        AuditService.record("update", role, request=request, old_data=diff_old, new_data=diff_new)
    return role
