"""缺陷业务服务：创建 / 状态机更新（含时间戳）/ 归档 / 关联 / 时间线。"""
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.defects.models import Defect, RequirementDefect, TestCaseDefect
from apps.projects.services.keys import next_key
from apps.requirements.models import Requirement
from apps.testcases.models import TestCase
from common.exceptions import PermissionDeniedError
from common.optimistic import save_with_lock
from common.statemachine import validate_transition
from common.utils import model_diff, model_snapshot

TRACKED_FIELDS = [
    "title", "description", "severity", "priority", "status",
    "environment", "version", "assignee", "resolved_at", "closed_at",
]
UPDATE_FIELDS = [
    "title", "description", "severity", "priority", "status",
    "environment", "version", "assignee_id", "resolved_at", "closed_at",
]
REOPEN_STATUSES = {Defect.STATUS_REOPENED, Defect.STATUS_OPEN}


def record_audit(action, obj, request=None, **kwargs):
    """审计适配：请求缺 User-Agent 头时补空串（common/utils.user_agent 会返回 None，
    而 AuditLog.user_agent 非空）。建议后续在 common/utils.py 修复。"""
    if request is not None and request.META.get("HTTP_USER_AGENT") is None:
        request.META["HTTP_USER_AGENT"] = ""
    return AuditService.record(action, obj, request=request, **kwargs)


def _require_system_admin(user):
    if not (getattr(user, "is_superuser", False) or getattr(user, "is_system_admin", False)):
        raise PermissionDeniedError("仅系统管理员可归档缺陷")


def _resolve_test_cases(project, test_case_ids) -> list[TestCase]:
    ids = list(dict.fromkeys(test_case_ids))
    cases = list(TestCase.objects.filter(project=project, pk__in=ids))
    found = {case.pk for case in cases}
    missing = [pk for pk in ids if pk not in found]
    if missing:
        raise ValidationError(f"测试用例不存在或不属于当前项目: {missing}")
    return cases


def _resolve_requirements(project, requirement_ids) -> list[Requirement]:
    ids = list(dict.fromkeys(requirement_ids))
    requirements = list(Requirement.objects.filter(project=project, pk__in=ids))
    found = {req.pk for req in requirements}
    missing = [pk for pk in ids if pk not in found]
    if missing:
        raise ValidationError(f"需求不存在或不属于当前项目: {missing}")
    return requirements


@transaction.atomic
def create_defect(*, project, user, data: dict, request=None) -> Defect:
    """创建缺陷：同事务取 BUG 编号 + 落库 + 关联表 + 审计。"""
    defect = Defect(
        organization=project.organization,
        project=project,
        key=next_key(project, "BUG"),
        title=data["title"],
        description=data.get("description", ""),
        severity=data.get("severity", "Major"),
        priority=data.get("priority", "P1"),
        status=Defect.STATUS_OPEN,
        environment=data.get("environment", ""),
        version=data.get("version", ""),
        reporter=user,
        assignee=data.get("assignee"),
    )
    defect.save()

    for case in _resolve_test_cases(project, data.get("test_case_ids") or []):
        TestCaseDefect.objects.get_or_create(test_case=case, defect=defect)
    for requirement in _resolve_requirements(project, data.get("requirement_ids") or []):
        RequirementDefect.objects.get_or_create(requirement=requirement, defect=defect)

    record_audit(
        "create", defect, request=request, new_data=model_snapshot(defect, TRACKED_FIELDS + ["key"])
    )
    return defect


@transaction.atomic
def update_defect(*, defect: Defect, data: dict, expected_updated_at, request=None) -> Defect:
    """更新缺陷：乐观锁 + 状态机 + resolved_at/closed_at 自动维护 + 审计 diff。"""
    new_status = data.get("status")
    status_changed = new_status is not None and new_status != defect.status
    if status_changed:
        validate_transition("defect", defect.status, new_status)

    old_data = model_snapshot(defect, TRACKED_FIELDS)
    for field, value in data.items():
        setattr(defect, field, value)
    if status_changed:
        now = timezone.now()
        if new_status == Defect.STATUS_RESOLVED and defect.resolved_at is None:
            defect.resolved_at = now
        if new_status == Defect.STATUS_CLOSED:
            defect.closed_at = now
        if new_status in REOPEN_STATUSES:
            defect.closed_at = None
    new_data = model_snapshot(defect, TRACKED_FIELDS)

    save_with_lock(defect, expected_updated_at, update_fields=UPDATE_FIELDS)

    old_diff, new_diff = model_diff(old_data, new_data)
    record_audit(
        "transition" if status_changed else "update",
        defect, request=request, old_data=old_diff, new_data=new_diff,
    )
    return defect


@transaction.atomic
def archive_defect(*, defect: Defect, user, request=None) -> Defect:
    """D9a 归档：不物理删，状态置 Closed + closed_at + 审计。仅系统管理员。"""
    _require_system_admin(user)
    old_status = defect.status
    defect.status = Defect.STATUS_CLOSED
    if defect.closed_at is None:
        defect.closed_at = timezone.now()
    defect.save(update_fields=["status", "closed_at", "updated_at"])
    record_audit(
        "delete", defect, request=request,
        old_data={"status": old_status} if old_status != defect.status else {},
        new_data={"archived": True, "status": Defect.STATUS_CLOSED},
    )
    return defect


# ---------------------------------------------------------------- 关联
@transaction.atomic
def link_testcases(*, defect: Defect, test_case_ids, request=None) -> list[int]:
    cases = _resolve_test_cases(defect.project, test_case_ids)
    linked = []
    for case in cases:
        _, created = TestCaseDefect.objects.get_or_create(test_case=case, defect=defect)
        if created:
            linked.append(case.pk)
    if linked:
        record_audit("link", defect, request=request, new_data={"test_case_ids": linked})
    return linked


@transaction.atomic
def unlink_testcase(*, defect: Defect, test_case_id, request=None) -> bool:
    deleted, _ = TestCaseDefect.objects.filter(defect=defect, test_case_id=test_case_id).delete()
    if deleted:
        record_audit("unlink", defect, request=request, new_data={"test_case_ids": [test_case_id]})
    return bool(deleted)


@transaction.atomic
def link_requirements(*, defect: Defect, requirement_ids, request=None) -> list[int]:
    requirements = _resolve_requirements(defect.project, requirement_ids)
    linked = []
    for requirement in requirements:
        _, created = RequirementDefect.objects.get_or_create(requirement=requirement, defect=defect)
        if created:
            linked.append(requirement.pk)
    if linked:
        record_audit("link", defect, request=request, new_data={"requirement_ids": linked})
    return linked


@transaction.atomic
def unlink_requirement(*, defect: Defect, requirement_id, request=None) -> bool:
    deleted, _ = RequirementDefect.objects.filter(defect=defect, requirement_id=requirement_id).delete()
    if deleted:
        record_audit("unlink", defect, request=request, new_data={"requirement_ids": [requirement_id]})
    return bool(deleted)


# ---------------------------------------------------------------- 状态时间线
def defect_timeline(defect: Defect) -> list[dict]:
    """状态时间线：来自 AuditLog(object_type="defect")，按时间升序。"""
    dt = serializers.DateTimeField()
    logs = (
        AuditLog.objects.filter(object_type="defect", object_id=defect.pk)
        .select_related("user")
        .order_by("created_at", "id")
    )
    timeline = []
    for log in logs:
        user = log.user
        timeline.append({
            "id": log.id,
            "action": log.action,
            "from_status": (log.old_data or {}).get("status"),
            "to_status": (log.new_data or {}).get("status"),
            "user": (
                {"id": user.pk, "username": user.username, "display_name": user.display_name}
                if user else None
            ),
            "created_at": dt.to_representation(log.created_at),
        })
    return timeline
