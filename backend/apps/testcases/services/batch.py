"""批量操作（§57）：逐条独立事务 + 逐条审计，返回 {succeeded, failed}。"""
from django.db import transaction

from apps.audit.services import AuditService
from apps.testcases.models import TestCase, TestCaseTag
from apps.testcases.services.cases import (
    _audit_snapshot,
    resolve_module,
    resolve_owner,
    resolve_tags,
)
from common.exceptions import NanoAPIError
from common.statemachine import validate_transition
from common.utils import model_diff

OPS = ["update", "move", "tag", "delete", "restore"]


def run_batch(project, op: str, test_case_ids: list[int], params: dict, user, request=None) -> dict:
    succeeded: list[int] = []
    failed: list[dict] = []
    for case_id in test_case_ids:
        try:
            with transaction.atomic():
                case = (
                    TestCase.all_objects
                    .select_related("project", "organization", "module", "owner", "creator")
                    .filter(project=project, pk=case_id)
                    .first()
                )
                if case is None:
                    raise NanoAPIError("测试用例不存在")
                _apply(case, op, params or {}, user, request)
                succeeded.append(case_id)
        except NanoAPIError as exc:
            failed.append({"id": case_id, "reason": exc.message})
        except Exception as exc:  # 单条失败不拖垮整批
            failed.append({"id": case_id, "reason": str(exc)})
    return {"succeeded": succeeded, "failed": failed}


def _apply(case, op: str, params: dict, user, request=None):
    if op == "update":
        _apply_update(case, params, user, request)
    elif op == "move":
        old_data = {"module": case.module_id}
        case.module = resolve_module(case.project, params.get("module_id"))
        case.save(update_fields=["module", "updated_at"])
        AuditService.record("update", case, request=request, user=user,
                            old_data=old_data, new_data={"module": case.module_id})
    elif op == "tag":
        _apply_tag(case, params, user, request)
    elif op == "delete":
        if case.is_deleted:
            raise NanoAPIError("用例已删除")
        snapshot = _audit_snapshot(case, list(case.tags.values_list("id", flat=True)), None, None)
        case.soft_delete()
        AuditService.record("delete", case, request=request, user=user, old_data=snapshot)
    elif op == "restore":
        if not case.is_deleted:
            raise NanoAPIError("用例未删除，无需恢复")
        old_data = {"deleted_at": case.deleted_at.isoformat() if case.deleted_at else None}
        case.restore()
        AuditService.record("update", case, request=request, user=user,
                            old_data=old_data, new_data={"deleted_at": None})
    else:
        raise NanoAPIError(f"不支持的批量操作: {op}")


def _apply_update(case, params: dict, user, request=None):
    allowed = {"priority", "owner_id", "status"}
    unknown = set(params) - allowed
    if unknown:
        raise NanoAPIError(f"update 参数不支持: {', '.join(sorted(unknown))}")

    old_snapshot = _audit_snapshot(case, list(case.tags.values_list("id", flat=True)), None, None)
    if "priority" in params:
        if params["priority"] not in {choice[0] for choice in TestCase.PRIORITY_CHOICES}:
            raise NanoAPIError(f"priority 参数非法: {params['priority']}")
        case.priority = params["priority"]
    if "status" in params and params["status"] != case.status:
        validate_transition("testcase", case.status, params["status"])
        case.status = params["status"]
    if "owner_id" in params:
        case.owner = resolve_owner(params["owner_id"])

    case.save(update_fields=["priority", "status", "owner", "updated_at"])
    new_snapshot = _audit_snapshot(case, list(case.tags.values_list("id", flat=True)), None, None)
    old_diff, new_diff = model_diff(old_snapshot, new_snapshot)
    AuditService.record("update", case, request=request, user=user,
                        old_data=old_diff or None, new_data=new_diff or None)


def _apply_tag(case, params: dict, user, request=None):
    allowed = {"add_tag_ids", "remove_tag_ids"}
    unknown = set(params) - allowed
    if unknown:
        raise NanoAPIError(f"tag 参数不支持: {', '.join(sorted(unknown))}")

    add_tags = resolve_tags(case.project, params.get("add_tag_ids") or [])
    remove_tags = resolve_tags(case.project, params.get("remove_tag_ids") or [])
    old_tag_ids = sorted(case.tags.values_list("id", flat=True))

    existing = set(TestCaseTag.objects.filter(test_case=case).values_list("tag_id", flat=True))
    TestCaseTag.objects.bulk_create(
        [TestCaseTag(test_case=case, tag=tag) for tag in add_tags if tag.id not in existing]
    )
    if remove_tags:
        TestCaseTag.objects.filter(test_case=case, tag__in=remove_tags).delete()

    new_tag_ids = sorted(case.tags.values_list("id", flat=True))
    if new_tag_ids != old_tag_ids:
        AuditService.record(
            "update", case, request=request, user=user,
            old_data={"tag_ids": old_tag_ids}, new_data={"tag_ids": new_tag_ids},
        )
