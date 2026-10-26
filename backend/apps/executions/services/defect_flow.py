"""FAIL→缺陷事务（§34、§51）：TestResult + Defect + TestResultDefect + TestCaseDefect 同事务。"""
from django.db import transaction

from apps.audit.services import AuditService
from apps.defects.models import Defect, TestCaseDefect, TestResultDefect
from apps.executions.models import TestResult
from apps.projects.services.keys import next_key


def create_defect_from_result(request, result: TestResult, data: dict) -> Defect:
    run = result.test_run
    case = result.test_case
    description = data.get("description") or _default_description(result)
    if data.get("comment"):
        description = f"{description}\n\n备注：{data['comment']}"
    with transaction.atomic():
        defect = Defect.objects.create(
            organization=run.organization,
            project=run.project,
            key=next_key(run.project, "BUG"),
            title=(data.get("title") or f"[失败] {case.case_key} {case.title}")[:255],
            description=description,
            severity=data.get("severity", "Major"),
            priority=data.get("priority", "P1"),
            status=Defect.STATUS_OPEN,
            environment=data.get("environment") or run.environment,
            version=data.get("version") or run.build_version,
            reporter=request.user,
        )
        TestResultDefect.objects.create(test_result=result, defect=defect)
        TestCaseDefect.objects.create(test_case=case, defect=defect)
        AuditService.record(
            "create", defect, request=request, old_data=None,
            new_data={"key": defect.key, "title": defect.title, "test_result": result.pk},
        )
    return defect


def _default_description(result: TestResult) -> str:
    run = result.test_run
    version = result.test_case_version
    lines = [
        f"用例：{result.test_case.case_key} {version.title}",
        f"执行轮次：{run.name}（环境 {run.environment or '-'} / 版本 {run.build_version or '-'}）",
        "",
    ]
    if version.precondition:
        lines += ["前置条件：", version.precondition, ""]
    lines.append("步骤：")
    for step in sorted(version.steps or [], key=lambda item: item.get("order", 0)):
        lines.append(f"{step.get('order', '')}. {step.get('action', '')}")
        if step.get("expected"):
            lines.append(f"   预期结果：{step['expected']}")
    if version.expected_result:
        lines += ["", f"预期结果：{version.expected_result}"]
    lines += ["", f"实际结果：{result.actual_result or '（未填写）'}"]
    return "\n".join(lines)
