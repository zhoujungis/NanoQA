"""报告测试数据构造。"""
from django.utils import timezone

from apps.accounts.models import User
from apps.defects.models import Defect, TestResultDefect
from apps.executions.models import TestResult, TestRun
from apps.organizations.models import Organization
from apps.projects.models import Module, Project
from apps.projects.services.keys import next_key
from apps.requirements.models import Requirement, RequirementTestCase
from apps.testcases.models import TestCase, TestCaseVersion
from apps.testplans.models import TestPlan


def make_user(username: str = "qa") -> User:
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password="pwd", is_system_admin=True
    )


def make_project(user: User, key: str = "SHOP") -> Project:
    org = Organization.objects.create(name="演示组织", slug=f"org-{key.lower()}", owner=user)
    return Project.objects.create(organization=org, name="商城项目", key=key, owner=user)


def make_module(project: Project, name: str) -> Module:
    return Module.objects.create(project=project, name=name)


def make_case(project: Project, user: User, title: str = "默认用例", priority: str = "P1",
              module: Module | None = None, steps=None) -> TestCase:
    case = TestCase.objects.create(
        organization=project.organization, project=project, case_key=next_key(project, "TC"),
        title=title, priority=priority, creator=user, module=module, status=TestCase.STATUS_ACTIVE,
    )
    TestCaseVersion.objects.create(
        test_case=case, version=1, title=title,
        steps=steps or [{"order": 1, "action": "打开页面", "expected": "加载成功"}],
        expected_result="符合预期", created_by=user,
    )
    return case


def make_plan_and_run(project: Project, user: User, name: str = "回归计划") -> tuple[TestPlan, TestRun]:
    plan = TestPlan.objects.create(organization=project.organization, project=project, name=name, created_by=user)
    run = TestRun.objects.create(
        organization=project.organization, project=project, test_plan=plan,
        name=f"{name}-Run", created_by=user, started_at=timezone.now(),
    )
    return plan, run


def make_result(run: TestRun, case: TestCase, status: str, user: User | None = None) -> TestResult:
    return TestResult.objects.create(
        test_run=run, test_case=case, test_case_version=case.versions.first(),
        status=status, executed_by=user, executed_at=timezone.now(),
    )


def make_defect(project: Project, user: User, title: str = "登录失败", severity: str = "Major",
                status: str = "Open") -> Defect:
    return Defect.objects.create(
        organization=project.organization, project=project, key=next_key(project, "BUG"),
        title=title, severity=severity, status=status, reporter=user,
    )


def link_result_defect(result: TestResult, defect: Defect) -> TestResultDefect:
    return TestResultDefect.objects.create(test_result=result, defect=defect)


def make_requirement(project: Project, user: User, title: str = "用户登录", covered: bool = False) -> Requirement:
    requirement = Requirement.objects.create(
        organization=project.organization, project=project, key=next_key(project, "REQ"),
        title=title, creator=user,
    )
    if covered:
        case = make_case(project, user, title=f"{title}-覆盖用例")
        RequirementTestCase.objects.create(requirement=requirement, test_case=case)
    return requirement
