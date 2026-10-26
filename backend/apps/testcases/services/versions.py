"""用例版本快照：历史执行结果必须绑定版本（坑 4）。"""
from apps.testcases.models import TestCaseVersion

# 触发新版本的内容字段
CONTENT_FIELDS = ["title", "precondition", "steps", "expected_result", "description"]


def get_current_version(case) -> TestCaseVersion:
    return case.versions.get(version=case.current_version)


def create_version(case, *, version: int, title: str, description: str, precondition: str,
                   steps: list, expected_result: str, change_summary: str, created_by) -> TestCaseVersion:
    return TestCaseVersion.objects.create(
        test_case=case,
        version=version,
        title=title,
        description=description,
        precondition=precondition,
        steps=steps,
        expected_result=expected_result,
        change_summary=change_summary,
        created_by=created_by,
    )
