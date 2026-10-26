"""项目 Dashboard 聚合（§35/§74）。

口径（与 §35 一致，必须单测）：
- executed = 非 not_run 的用例数（每个用例取最近一次 TestResult 状态，无结果记 not_run）
- execution_rate = executed / total_cases
- pass_rate = passed / executed（not_run 不进分母）
- failure_rate = failed / executed；block_rate = blocked / executed
"""
from django.db.models import Count, F, Max

from apps.defects.models import Defect
from apps.executions.models import TestResult
from apps.projects.models import Project
from apps.requirements.models import Requirement, RequirementTestCase
from apps.testcases.models import TestCase
from apps.testplans.models import TestPlan

RECENT_PLAN_LIMIT = 5
RECENT_FAILURE_LIMIT = 10


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def build_dashboard(project: Project) -> dict:
    case_qs = TestCase.objects.filter(project=project)
    total_cases = case_qs.count()
    by_status = {row["status"]: row["n"] for row in case_qs.values("status").annotate(n=Count("id"))}
    by_priority = {row["priority"]: row["n"] for row in case_qs.values("priority").annotate(n=Count("id"))}

    return {
        "total_cases": total_cases,
        "cases_by_status": by_status,
        "cases_by_priority": by_priority,
        "execution": _execution_stats(project, total_cases),
        "defects": _defect_stats(project),
        "requirement_coverage": _requirement_coverage(project),
        "recent_plans": _recent_plans(project),
        "recent_failures": _recent_failures(project),
    }


def _execution_stats(project: Project, total_cases: int) -> dict:
    # 每个用例取最近一条 TestResult（Max(id)）作为当前执行状态，2 条聚合查询
    latest_ids = (
        TestResult.objects.filter(test_case__project=project)
        .values("test_case_id")
        .annotate(latest_id=Max("id"))
        .values("latest_id")
    )
    counts = {
        row["status"]: row["n"]
        for row in TestResult.objects.filter(id__in=latest_ids).values("status").annotate(n=Count("id"))
    }
    passed = counts.get("passed", 0)
    failed = counts.get("failed", 0)
    blocked = counts.get("blocked", 0)
    skipped = counts.get("skipped", 0)
    executed = passed + failed + blocked + skipped
    not_run = total_cases - executed
    return {
        "executed": executed,
        "not_run": not_run,
        "passed": passed,
        "failed": failed,
        "blocked": blocked,
        "skipped": skipped,
        "execution_rate": _ratio(executed, total_cases),
        "pass_rate": _ratio(passed, executed),
        "failure_rate": _ratio(failed, executed),
        "block_rate": _ratio(blocked, executed),
    }


def _defect_stats(project: Project) -> dict:
    defect_qs = Defect.objects.filter(project=project)
    by_status = {row["status"]: row["n"] for row in defect_qs.values("status").annotate(n=Count("id"))}
    by_severity = {row["severity"]: row["n"] for row in defect_qs.values("severity").annotate(n=Count("id"))}
    return {
        "total": sum(by_status.values()),
        "open": by_status.get("Open", 0),
        "in_progress": by_status.get("In Progress", 0),
        "resolved": by_status.get("Resolved", 0),
        "closed": by_status.get("Closed", 0),
        "by_severity": by_severity,
    }


def _requirement_coverage(project: Project) -> dict:
    total = Requirement.objects.filter(project=project).count()
    covered = (
        RequirementTestCase.objects.filter(requirement__project=project)
        .values("requirement_id")
        .distinct()
        .count()
    )
    return {"total": total, "covered": covered, "rate": _ratio(covered, total)}


def _recent_plans(project: Project) -> list[dict]:
    return list(
        TestPlan.objects.filter(project=project)
        .order_by("-updated_at")
        .values("name", "status", "updated_at")[:RECENT_PLAN_LIMIT]
    )


def _recent_failures(project: Project) -> list[dict]:
    # 坑 4：标题取执行时绑定的版本快照
    results = (
        TestResult.objects.filter(test_case__project=project, status="failed")
        .select_related("test_case", "test_case_version")
        .order_by(F("executed_at").desc(nulls_last=True), "-id")[:RECENT_FAILURE_LIMIT]
    )
    return [
        {
            "case_key": result.test_case.case_key,
            "title": result.test_case_version.title,
            "executed_at": result.executed_at,
        }
        for result in results
    ]
