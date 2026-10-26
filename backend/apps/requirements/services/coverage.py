"""需求覆盖率（设计文档 §37）。

v0.1 口径：coverage = linked_test_cases / expected_test_cases；
expected 缺省取 linked_cases（即 100%）。
执行数据取 TestResult 中每个用例最新一次结果。
risk_level：无关联=high、有 failed/blocked=medium、全 passed=low。
"""
from apps.executions.models import TestResult
from apps.requirements.models import RequirementTestCase

EXECUTED_STATUSES = {"passed", "failed", "blocked", "skipped"}


def latest_results(case_ids) -> list[TestResult]:
    """每个用例最新一次执行结果（按 id 递增取最新）。"""
    if not case_ids:
        return []
    return list(
        TestResult.objects.filter(test_case_id__in=case_ids)
        .order_by("test_case_id", "-id")
        .distinct("test_case_id")
    )


def requirement_coverage(requirement, expected_cases: int | None = None) -> dict:
    case_ids = list(
        RequirementTestCase.objects.filter(
            requirement=requirement, test_case__deleted_at__isnull=True
        ).values_list("test_case_id", flat=True)
    )
    linked_cases = len(case_ids)

    results = latest_results(case_ids)
    passed = sum(1 for r in results if r.status == "passed")
    failed = sum(1 for r in results if r.status == "failed")
    blocked = sum(1 for r in results if r.status == "blocked")
    skipped = sum(1 for r in results if r.status == "skipped")
    executed = sum(1 for r in results if r.status in EXECUTED_STATUSES)
    not_run = linked_cases - executed

    expected = linked_cases if expected_cases is None else expected_cases
    coverage = round(linked_cases / expected, 4) if expected else 0.0

    if linked_cases == 0:
        risk_level = "high"
    elif failed or blocked:
        risk_level = "medium"
    elif passed == linked_cases:
        risk_level = "low"
    else:
        risk_level = "medium"

    return {
        "linked_cases": linked_cases,
        "expected_cases": expected,
        "executed": executed,
        "passed": passed,
        "failed": failed,
        "blocked": blocked,
        "skipped": skipped,
        "not_run": not_run,
        "coverage": coverage,
        "risk_level": risk_level,
    }
