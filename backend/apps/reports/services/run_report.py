"""TestRun 报告聚合（§36）：总览 / 模块分析 / 失败用例 / 缺陷统计。

口径：pass_rate = passed / executed（not_run 不进分母，与 Dashboard 一致）；
失败用例标题一律取 TestResult.test_case_version 版本快照（坑 4）。
"""
from django.db.models import Count, Prefetch, Q

from apps.defects.models import Defect, TestResultDefect
from apps.executions.models import TestResult, TestRun
from apps.projects.models import Project

UNCATEGORIZED = "未分类"


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def build_run_report(run: TestRun) -> dict:
    results = TestResult.objects.filter(test_run=run)
    counts = {row["status"]: row["n"] for row in results.values("status").annotate(n=Count("id"))}
    total = sum(counts.values())
    passed = counts.get("passed", 0)
    failed = counts.get("failed", 0)
    blocked = counts.get("blocked", 0)
    skipped = counts.get("skipped", 0)
    executed = total - counts.get("not_run", 0)

    return {
        "run_id": run.id,
        "name": run.name,
        "status": run.status,
        "overview": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "skipped": skipped,
            "pass_rate": _ratio(passed, executed),
        },
        "module_analysis": _module_analysis(results),
        "failed_cases": _failed_cases(results),
        "defect_stats": _defect_stats(run),
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "environment": run.environment,
        "build_version": run.build_version,
    }


def _module_analysis(results) -> list[dict]:
    rows = (
        results.values("test_case__module_id", "test_case__module__name")
        .annotate(
            total=Count("id"),
            passed=Count("id", filter=Q(status="passed")),
            not_run=Count("id", filter=Q(status="not_run")),
        )
        .order_by("-total", "test_case__module_id")
    )
    return [
        {
            "module_id": row["test_case__module_id"],
            "module_name": row["test_case__module__name"] or UNCATEGORIZED,
            "total": row["total"],
            "passed": row["passed"],
            "pass_rate": _ratio(row["passed"], row["total"] - row["not_run"]),
        }
        for row in rows
    ]


def _failed_cases(results) -> list[dict]:
    failed = (
        results.filter(status="failed")
        .select_related("test_case", "test_case_version", "test_case__module", "executed_by")
        .prefetch_related(
            Prefetch("testresultdefect_set", queryset=TestResultDefect.objects.select_related("defect"))
        )
        .order_by("id")
    )
    return [
        {
            "result_id": result.id,
            "case_key": result.test_case.case_key,
            "title": result.test_case_version.title,
            "module": (result.test_case.module.name if result.test_case.module else UNCATEGORIZED),
            "executor": _executor_name(result),
            "executed_at": result.executed_at,
            "defects": [
                {"key": link.defect.key, "title": link.defect.title, "status": link.defect.status}
                for link in result.testresultdefect_set.all()
            ],
        }
        for result in failed
    ]


def _executor_name(result: TestResult) -> str:
    user = result.executed_by
    if user is None:
        return ""
    return user.display_name or user.username


def _defect_stats(run: TestRun) -> dict:
    defect_qs = Defect.objects.filter(testresultdefect__test_result__test_run=run).distinct()
    by_status = {
        row["status"]: row["n"]
        for row in defect_qs.values("status").annotate(n=Count("id", distinct=True))
    }
    by_severity = {
        row["severity"]: row["n"]
        for row in defect_qs.values("severity").annotate(n=Count("id", distinct=True))
    }
    return {
        "total": sum(by_status.values()),
        "open": by_status.get("Open", 0),
        "in_progress": by_status.get("In Progress", 0),
        "resolved": by_status.get("Resolved", 0),
        "closed": by_status.get("Closed", 0),
        "by_severity": by_severity,
    }


def run_summaries(project: Project):
    """历史 run 报告列表：单条 GROUP BY 出各状态计数，供分页列表用。"""
    return (
        TestRun.objects.filter(project=project)
        .annotate(
            total=Count("results", distinct=True),
            passed=Count("results", filter=Q(results__status="passed"), distinct=True),
            failed=Count("results", filter=Q(results__status="failed"), distinct=True),
            not_run=Count("results", filter=Q(results__status="not_run"), distinct=True),
        )
        .order_by("-created_at")
    )
