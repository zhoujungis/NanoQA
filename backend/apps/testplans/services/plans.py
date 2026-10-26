"""测试计划服务（§16-17）：计划维护、计划用例管理、start 事务建 Run。"""
from django.db import transaction

from apps.audit.services import AuditService
from apps.executions.services import runner as runner_service
from apps.testcases.models import TestCase
from apps.testplans.models import TestPlan, TestPlanCase
from common.exceptions import BusinessConflictError, NotFoundError
from common.optimistic import save_with_lock
from common.statemachine import validate_transition
from common.utils import model_diff, model_snapshot

PLAN_DIFF_FIELDS = ["name", "description", "version", "status", "start_at", "end_at", "owner"]


def create_plan(request, project, data) -> TestPlan:
    with transaction.atomic():
        plan = TestPlan.objects.create(
            organization=project.organization,
            project=project,
            name=data["name"],
            description=data.get("description", ""),
            version=data.get("version", ""),
            start_at=data.get("start_at"),
            end_at=data.get("end_at"),
            owner=data.get("owner"),
            created_by=request.user,
        )
        AuditService.record(
            "create", plan, request=request,
            old_data=None, new_data=model_snapshot(plan, fields=PLAN_DIFF_FIELDS),
        )
    return plan


def update_plan(request, plan, validated, expected_updated_at) -> TestPlan:
    """更新计划：status 走状态机，updated_at 乐观锁。"""
    with transaction.atomic():
        new_status = validated.get("status")
        if new_status is not None and new_status != plan.status:
            validate_transition("testplan", plan.status, new_status)
        old_snapshot = model_snapshot(plan, fields=PLAN_DIFF_FIELDS)
        for field, value in validated.items():
            setattr(plan, field, value)
        save_with_lock(plan, expected_updated_at, list(validated.keys()))
        new_snapshot = model_snapshot(plan, fields=PLAN_DIFF_FIELDS)
        old_data, new_data = model_diff(old_snapshot, new_snapshot)
        action = "transition" if "status" in new_data else "update"
        AuditService.record(action, plan, request=request, old_data=old_data, new_data=new_data)
    return plan


def cancel_plan(request, plan) -> TestPlan:
    """DELETE = 置 cancelled + 审计，不物理删除（§48）。"""
    with transaction.atomic():
        validate_transition("testplan", plan.status, TestPlan.STATUS_CANCELLED)
        old_status = plan.status
        plan.status = TestPlan.STATUS_CANCELLED
        plan.save(update_fields=["status", "updated_at"])
        AuditService.record(
            "delete", plan, request=request,
            old_data={"status": old_status}, new_data={"status": TestPlan.STATUS_CANCELLED},
        )
    return plan


def add_cases(request, plan, test_case_ids, assigned_to=None) -> dict:
    """批量加入计划用例：已存在跳过，priority 从用例拷贝。"""
    unique_ids = list(dict.fromkeys(test_case_ids))
    cases = {
        case.pk: case
        for case in TestCase.objects.filter(project=plan.project, pk__in=unique_ids)
    }
    missing = [pk for pk in unique_ids if pk not in cases]
    if missing:
        raise NotFoundError(f"测试用例不存在: {missing}")
    existing = set(
        TestPlanCase.objects.filter(test_plan=plan, test_case_id__in=unique_ids)
        .values_list("test_case_id", flat=True)
    )
    added, skipped = [], []
    with transaction.atomic():
        for pk in unique_ids:
            if pk in existing:
                skipped.append(pk)
                continue
            case = cases[pk]
            TestPlanCase.objects.create(
                test_plan=plan,
                test_case=case,
                priority=case.priority,
                assigned_to=assigned_to,
                execution_status="not_run",
            )
            added.append(pk)
        AuditService.record(
            "link", plan, request=request, old_data=None,
            new_data={"added": added, "skipped": skipped},
        )
    return {"added": added, "skipped": skipped}


def update_plan_case(request, plan, test_case_id, data) -> TestPlanCase:
    link = _plan_case(plan, test_case_id)
    with transaction.atomic():
        old_data = {"assigned_to": link.assigned_to_id, "priority": link.priority}
        if "assigned_to" in data:
            link.assigned_to = data["assigned_to"]
        if "priority" in data:
            link.priority = data["priority"]
        link.save(update_fields=["assigned_to", "priority", "updated_at"])
        new_data = {"assigned_to": link.assigned_to_id, "priority": link.priority}
        AuditService.record(
            "update", link, request=request, old_data=old_data, new_data=new_data,
            object_ref=link.test_case.case_key,
            project=plan.project, organization=plan.organization,
        )
    return link


def remove_plan_case(request, plan, test_case_id) -> None:
    link = _plan_case(plan, test_case_id)
    with transaction.atomic():
        link.delete()
        AuditService.record(
            "unlink", plan, request=request,
            old_data={"test_case_id": test_case_id}, new_data=None,
        )


def _plan_case(plan, test_case_id) -> TestPlanCase:
    link = (
        TestPlanCase.objects.select_related("test_case", "assigned_to")
        .filter(test_plan=plan, test_case_id=test_case_id)
        .first()
    )
    if link is None:
        raise NotFoundError("计划用例不存在")
    return link


def start_plan(request, plan, data) -> "TestRun":  # noqa: F821 - 循环引用仅为类型提示
    """开始执行：draft→ready→running（或 ready→running），事务内建 Run + 预建结果。"""
    old_status = plan.status
    with transaction.atomic():
        if plan.status == TestPlan.STATUS_DRAFT:
            validate_transition("testplan", TestPlan.STATUS_DRAFT, TestPlan.STATUS_READY)
            plan.status = TestPlan.STATUS_READY
        if plan.status == TestPlan.STATUS_READY:
            validate_transition("testplan", TestPlan.STATUS_READY, TestPlan.STATUS_RUNNING)
            plan.status = TestPlan.STATUS_RUNNING
        else:
            validate_transition("testplan", plan.status, TestPlan.STATUS_RUNNING)
            raise BusinessConflictError("计划已开始执行，请通过「新增执行轮次」创建 TestRun")
        plan.save(update_fields=["status", "updated_at"])
        run = runner_service.create_run_with_results(request, plan, data)
        AuditService.record(
            "transition", plan, request=request,
            old_data={"status": old_status}, new_data={"status": plan.status, "run_id": run.pk},
        )
    return run


def create_run(request, plan, data):
    """基于计划再开一轮执行（回归复测）。"""
    if plan.status not in (TestPlan.STATUS_RUNNING, TestPlan.STATUS_COMPLETED):
        raise BusinessConflictError("计划状态须为执行中或已完成，才能新增执行轮次")
    with transaction.atomic():
        return runner_service.create_run_with_results(request, plan, data)
