"""模块树服务：树构建、增改、移动（环检测）、删除保护（§51）。"""
from django.db import transaction
from django.db.models import Count

from apps.audit.services import AuditService
from apps.projects.models import Module, Project
from apps.testcases.models import TestCase
from common.exceptions import BusinessConflictError, NanoAPIError, NotFoundError
from common.optimistic import save_with_lock
from common.utils import model_diff, model_snapshot

MODULE_FIELDS = ["name", "description", "sort_order"]
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"


def module_tree(project: Project) -> list[dict]:
    """嵌套模块树 [{id,name,description,parent_id,sort_order,children,case_count,updated_at}]。"""
    modules = list(Module.objects.filter(project=project).order_by("sort_order", "id"))
    counts = {
        row["module_id"]: row["case_count"]
        for row in TestCase.objects.filter(project=project)
        .values("module_id")
        .annotate(case_count=Count("id"))
    }
    nodes: dict[int, dict] = {}
    for module in modules:
        nodes[module.pk] = {
            "id": module.pk,
            "name": module.name,
            "description": module.description,
            "parent_id": module.parent_id,
            "sort_order": module.sort_order,
            "children": [],
            "case_count": counts.get(module.pk, 0),
            "updated_at": module.updated_at.strftime(DATETIME_FORMAT),
        }
    roots: list[dict] = []
    for module in modules:
        node = nodes[module.pk]
        parent = nodes.get(module.parent_id)
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)
    return roots


def _resolve_parent(project: Project, parent) -> Module | None:
    if parent is None:
        return None
    if parent.project_id != project.pk:
        raise BusinessConflictError("父模块必须属于同一项目")
    return parent


def create_module(project: Project, data: dict, request=None) -> Module:
    parent = _resolve_parent(project, data.get("parent"))
    with transaction.atomic():
        module = Module.objects.create(
            project=project,
            parent=parent,
            name=data["name"],
            description=data.get("description", ""),
            sort_order=data.get("sort_order", 0),
        )
        AuditService.record(
            "create", module, request=request, project=project,
            new_data=model_snapshot(module, fields=["name", "description", "sort_order", "parent"]),
        )
    return module


def update_module(module: Module, data: dict, expected_updated_at, request=None) -> Module:
    new_parent = data.get("parent", module.parent)
    if new_parent is not None and new_parent.pk != module.parent_id:
        raise NanoAPIError("请使用 /api/v1/modules/{id}/move/ 调整模块层级")
    old_data = model_snapshot(module, fields=MODULE_FIELDS)
    for field in MODULE_FIELDS:
        if field in data:
            setattr(module, field, data[field])
    update_fields = [f for f in MODULE_FIELDS if f in data] or ["name"]
    with transaction.atomic():
        save_with_lock(module, expected_updated_at, update_fields)
        new_data = model_snapshot(module, fields=MODULE_FIELDS)
        diff_old, diff_new = model_diff(old_data, new_data)
        AuditService.record("update", module, request=request, project=module.project,
                            old_data=diff_old, new_data=diff_new)
    return module


def move_module(module: Module, parent_id, sort_order, request=None) -> Module:
    parent = None
    if parent_id is not None:
        parent = Module.objects.filter(pk=parent_id).first()
        if parent is None:
            raise NotFoundError("父模块不存在")
        if parent.project_id != module.project_id:
            raise BusinessConflictError("父模块必须属于同一项目")
        cursor = parent
        while cursor is not None:
            if cursor.pk == module.pk:
                raise BusinessConflictError("不能将模块移动到自身或其子模块下")
            cursor = cursor.parent
    old_data = {"parent_id": module.parent_id, "sort_order": module.sort_order}
    module.parent = parent
    if sort_order is not None:
        module.sort_order = sort_order
    with transaction.atomic():
        module.save(update_fields=["parent", "sort_order", "updated_at"])
        AuditService.record(
            "update", module, request=request, project=module.project,
            old_data=old_data,
            new_data={"parent_id": module.parent_id, "sort_order": module.sort_order},
        )
    return module


def delete_module(module: Module, request=None):
    """删除保护：存在子模块或测试用例（含软删，all_objects）→ 业务冲突；否则软删 + 审计。"""
    if Module.objects.filter(parent=module).exists():
        raise BusinessConflictError("模块下存在子模块或测试用例，禁止删除")
    if TestCase.all_objects.filter(module=module).exists():
        raise BusinessConflictError("模块下存在子模块或测试用例，禁止删除")
    with transaction.atomic():
        module.soft_delete()
        AuditService.record(
            "delete", module, request=request, project=module.project,
            old_data={"id": module.pk, "name": module.name},
        )
