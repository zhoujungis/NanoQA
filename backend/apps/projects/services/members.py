"""项目成员服务：绑定 / 角色变更 / 移除（均写审计）。"""
from django.db import transaction

from apps.accounts.models import Role, User
from apps.audit.services import AuditService
from apps.projects.models import Project, ProjectMember
from common.exceptions import BusinessConflictError, NotFoundError


def _check_role_scope(role: Role, project: Project):
    if role.organization_id not in (None, project.organization_id):
        raise BusinessConflictError("角色不属于该项目所属组织")


def get_project_member(member_id) -> ProjectMember:
    member = (
        ProjectMember.objects.filter(pk=member_id)
        .select_related("project", "user", "role")
        .first()
    )
    if member is None:
        raise NotFoundError("项目成员记录不存在")
    return member


def add_project_member(project: Project, user_id, role_id, request=None) -> ProjectMember:
    member_user = User.objects.filter(pk=user_id).first()
    if member_user is None:
        raise NotFoundError("用户不存在")
    role = Role.objects.filter(pk=role_id).first()
    if role is None:
        raise NotFoundError("角色不存在")
    _check_role_scope(role, project)
    if ProjectMember.objects.filter(project=project, user=member_user).exists():
        raise BusinessConflictError("该用户已是项目成员")
    with transaction.atomic():
        member = ProjectMember.objects.create(project=project, user=member_user, role=role)
        AuditService.record(
            "link", member, request=request, project=project,
            object_ref=f"{project.key}:user{member_user.pk}",
            new_data={"user_id": member_user.pk, "role_id": role.pk, "role_code": role.code},
        )
    return member


def update_project_member(member: ProjectMember, role_id, request=None) -> ProjectMember:
    role = Role.objects.filter(pk=role_id).first()
    if role is None:
        raise NotFoundError("角色不存在")
    _check_role_scope(role, member.project)
    old_role = member.role
    if role.pk == old_role.pk:
        return member
    with transaction.atomic():
        member.role = role
        member.save(update_fields=["role"])
        AuditService.record(
            "update", member, request=request, project=member.project,
            object_ref=f"{member.project.key}:user{member.user_id}",
            old_data={"role_id": old_role.pk, "role_code": old_role.code},
            new_data={"role_id": role.pk, "role_code": role.code},
        )
    return member


def remove_project_member(member: ProjectMember, request=None):
    with transaction.atomic():
        AuditService.record(
            "unlink", member, request=request, project=member.project,
            object_ref=f"{member.project.key}:user{member.user_id}",
            old_data={"user_id": member.user_id, "role_id": member.role_id, "role_code": member.role.code},
        )
        member.delete()
