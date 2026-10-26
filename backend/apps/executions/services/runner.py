"""执行服务（§18-19）：TestRun 创建（预建 not_run 结果）与结果提交（覆盖式 + 审计）。"""
from django.db import transaction
from django.db.models import Count, F
from django.utils import timezone

from apps.audit.services import AuditService
from apps.executions.models import TestResult, TestRun
from apps.testcases.models import TestCaseVersion
from apps.testplans.models import TestPlanCase
from common.exceptions import BusinessConflictError, NotFoundError

RESULT_DIFF_FIELDS = ["status", "actual_result", "comment", "duration"]
OPTIONAL_FIELDS = ["actual_result", "comment", "duration"]
RESULT_STATUSES = ["not_run", "passed", "failed", "blocked", "skipped"]


def run_detail(run: TestRun) -> dict:
    """Run 详情 + 结果统计（按 status 计数）。"""
    from apps.executions.serializers import TestRunSerializer

    counts = dict(
        run.results.values("status").annotate(total=Count("id")).values_list("status", "total")
    )
    stats = {"total": sum(counts.values())}
    stats.update({key: counts.get(key, 0) for key in RESULT_STATUSES})
    return {**TestRunSerializer(run).data, "project": run.project_id, "stats": stats}


def create_run_with_results(request, plan, data) -> TestRun:
    """为计划开一轮 Run，并为每个计划用例预建 not_run 结果。

    坑 4：结果必须绑定执行时的用例版本快照，这里绑当时的 current 版本对象，
    之后提交结果不再改绑。
    """
    plan_cases = list(plan.plan_cases.select_related("test_case"))
    if not plan_cases:
        raise BusinessConflictError("测试计划尚未添加用例，无法开始执行")
    case_ids = [plan_case.test_case_id for plan_case in plan_cases]
    version_map = {
        version.test_case_id: version
        for version in TestCaseVersion.objects.filter(
            test_case_id__in=case_ids, version=F("test_case__current_version")
        )
    }
    missing = [pk for pk in case_ids if pk not in version_map]
    if missing:
        raise BusinessConflictError(f"用例缺少版本快照，无法执行: {missing}")

    name = data.get("name") or f"{plan.name} {timezone.localtime().strftime('%Y%m%d-%H%M%S')}"
    run = TestRun.objects.create(
        organization=plan.organization,
        project=plan.project,
        test_plan=plan,
        name=name[:128],
        environment=data.get("environment", ""),
        build_version=data.get("build_version", ""),
        status=TestRun.STATUS_RUNNING,
        started_at=timezone.now(),
        created_by=request.user,
    )
    TestResult.objects.bulk_create([
        TestResult(
            test_run=run,
            test_case_id=pk,
            test_case_version=version_map[pk],
            status="not_run",
        )
        for pk in case_ids
    ])
    AuditService.record(
        "create", run, request=request,
        old_data=None, new_data={"name": run.name, "test_plan": plan.pk, "results": len(case_ids)},
    )
    return run


def submit_result(request, run, test_case_id, data) -> TestResult:
    with transaction.atomic():
        result = _get_result(run, test_case_id)
        _apply_result(request, run, result, data, update_executor=True)
    return result


def submit_results_bulk(request, run, items) -> list[TestResult]:
    with transaction.atomic():
        results = []
        for item in items:
            result = _get_result(run, item["test_case_id"])
            _apply_result(request, run, result, item, update_executor=True)
            results.append(result)
    return results


def update_result(request, result, data) -> TestResult:
    """修改单条结果：TestResult 无 updated_at，直接允许改并审计。"""
    run = result.test_run
    with transaction.atomic():
        _apply_result(request, run, result, data, update_executor=False, action="update")
    return result


def _get_result(run, test_case_id) -> TestResult:
    result = (
        TestResult.objects.select_related("test_case", "test_case_version", "test_run")
        .filter(test_run=run, test_case_id=test_case_id)
        .first()
    )
    if result is None:
        raise NotFoundError("执行结果不存在，请确认用例已加入该执行轮次")
    return result


def _apply_result(request, run, result, data, update_executor: bool, action: str = "execute"):
    """覆盖式更新（D3a）：同 case 再次提交覆盖旧值，审计记录前后状态。"""
    old_data = {field: getattr(result, field) for field in RESULT_DIFF_FIELDS}
    old_data["executed_by"] = result.executed_by_id

    changed = []
    if "status" in data:
        result.status = data["status"]
        changed.append("status")
    for field in OPTIONAL_FIELDS:
        if field in data:
            setattr(result, field, data[field])
            changed.append(field)
    if update_executor:
        result.executed_by = request.user
        result.executed_at = timezone.now()
        changed += ["executed_by", "executed_at"]
    if changed:
        result.save(update_fields=changed)

    if "status" in data:
        TestPlanCase.objects.filter(
            test_plan=run.test_plan, test_case_id=result.test_case_id
        ).update(execution_status=result.status)

    new_data = {field: getattr(result, field) for field in RESULT_DIFF_FIELDS}
    new_data["executed_by"] = result.executed_by_id
    AuditService.record(
        action, result, request=request, old_data=old_data, new_data=new_data,
        object_ref=result.test_case.case_key,
        project=run.project, organization=run.organization,
    )
