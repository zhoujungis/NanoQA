"""标签服务：项目内标签增改删。"""
from django.db import transaction

from apps.audit.services import AuditService
from apps.projects.models import Project, Tag
from common.exceptions import BusinessConflictError


def create_tag(project: Project, data: dict, request=None) -> Tag:
    name = (data["name"] or "").strip()
    if Tag.objects.filter(project=project, name=name).exists():
        raise BusinessConflictError("标签名已存在")
    with transaction.atomic():
        tag = Tag.objects.create(
            project=project, name=name, color=data.get("color", "#64748B")
        )
        AuditService.record(
            "create", tag, request=request, project=project,
            new_data={"name": tag.name, "color": tag.color},
        )
    return tag


def update_tag(tag: Tag, data: dict, request=None) -> Tag:
    name = (data.get("name") or tag.name).strip()
    if name != tag.name and Tag.objects.filter(project=tag.project, name=name).exists():
        raise BusinessConflictError("标签名已存在")
    old_data = {"name": tag.name, "color": tag.color}
    tag.name = name
    if "color" in data:
        tag.color = data["color"]
    with transaction.atomic():
        tag.save(update_fields=["name", "color"])
        AuditService.record(
            "update", tag, request=request, project=tag.project,
            old_data=old_data, new_data={"name": tag.name, "color": tag.color},
        )
    return tag


def remove_tag(tag: Tag, request=None):
    with transaction.atomic():
        AuditService.record(
            "delete", tag, request=request, project=tag.project,
            old_data={"id": tag.pk, "name": tag.name},
        )
        tag.delete()
