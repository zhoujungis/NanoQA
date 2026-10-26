"""需求业务服务：创建 / 更新（乐观锁+状态机）/ 软删 / 用例关联。"""
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit.services import AuditService
from apps.projects.services.keys import next_key
from apps.requirements.models import Requirement, RequirementTestCase
from apps.testcases.models import TestCase
from common.optimistic import save_with_lock
from common.statemachine import validate_transition
from common.utils import model_diff, model_snapshot

TRACKED_FIELDS = ["title", "description", "status", "priority", "owner"]
UPDATE_FIELDS = ["title", "description", "status", "priority", "owner_id"]


def record_audit(action, obj, request=None, **kwargs):
    """审计适配：请求缺 User-Agent 头时补空串（common/utils.user_agent 会返回 None，
    而 AuditLog.user_agent 非空）。建议后续在 common/utils.py 修复。"""
    if request is not None and request.META.get("HTTP_USER_AGENT") is None:
        request.META["HTTP_USER_AGENT"] = ""
    return AuditService.record(action, obj, request=request, **kwargs)


@transaction.atomic
def create_requirement(*, project, user, data: dict, request=None) -> Requirement:
    """创建需求：同事务取编号 + 落库 + 审计（§49/§51）。"""
    requirement = Requirement(
        organization=project.organization,
        project=project,
        key=next_key(project, "REQ"),
        title=data["title"],
        description=data.get("description", ""),
        status=data.get("status", Requirement.STATUS_DRAFT),
        priority=data.get("priority", "P1"),
        creator=user,
        owner=data.get("owner"),
        version=1,
    )
    requirement.save()
    record_audit(
        "create", requirement, request=request, new_data=model_snapshot(requirement, TRACKED_FIELDS + ["key", "status"])
    )
    return requirement


@transaction.atomic
def update_requirement(*, requirement: Requirement, data: dict, expected_updated_at, request=None) -> Requirement:
    """更新需求：乐观锁 + 状态机校验 + 审计 diff。"""
    new_status = data.get("status")
    status_changed = new_status is not None and new_status != requirement.status
    if status_changed:
        validate_transition("requirement", requirement.status, new_status)

    old_data = model_snapshot(requirement, TRACKED_FIELDS)
    for field, value in data.items():
        setattr(requirement, field, value)
    new_data = model_snapshot(requirement, TRACKED_FIELDS)

    save_with_lock(requirement, expected_updated_at, update_fields=UPDATE_FIELDS)

    old_diff, new_diff = model_diff(old_data, new_data)
    record_audit(
        "transition" if status_changed else "update",
        requirement, request=request, old_data=old_diff, new_data=new_diff,
    )
    return requirement


@transaction.atomic
def delete_requirement(*, requirement: Requirement, request=None):
    """软删除：质量资产不物理删（§48）。"""
    requirement.soft_delete()
    record_audit(
        "delete", requirement, request=request,
        new_data={"deleted": True, "deleted_at": requirement.deleted_at.isoformat()},
    )
    return requirement


def resolve_test_cases(project, test_case_ids) -> list[TestCase]:
    """校验用例存在（未软删）且属于同一项目。"""
    ids = list(dict.fromkeys(test_case_ids))
    cases = list(TestCase.objects.filter(project=project, pk__in=ids))
    found = {case.pk for case in cases}
    missing = [pk for pk in ids if pk not in found]
    if missing:
        raise ValidationError(f"测试用例不存在或不属于当前项目: {missing}")
    return cases


@transaction.atomic
def link_testcases(*, requirement: Requirement, test_case_ids, request=None) -> list[int]:
    cases = resolve_test_cases(requirement.project, test_case_ids)
    linked = []
    for case in cases:
        _, created = RequirementTestCase.objects.get_or_create(requirement=requirement, test_case=case)
        if created:
            linked.append(case.pk)
    if linked:
        record_audit("link", requirement, request=request, new_data={"test_case_ids": linked})
    return linked


@transaction.atomic
def unlink_testcase(*, requirement: Requirement, test_case_id, request=None) -> bool:
    deleted, _ = RequirementTestCase.objects.filter(
        requirement=requirement, test_case_id=test_case_id
    ).delete()
    if deleted:
        record_audit("unlink", requirement, request=request, new_data={"test_case_ids": [test_case_id]})
    return bool(deleted)
