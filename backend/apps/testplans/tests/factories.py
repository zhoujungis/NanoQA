"""测试数据构造器（仅测试使用）。"""
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.projects.models import Project
from apps.testcases.models import TestCase, TestCaseVersion
from apps.testplans.models import TestPlan, TestPlanCase

STEPS = [
    {"order": 1, "action": "打开登录页", "expected": "登录页正常显示"},
    {"order": 2, "action": "输入错误密码并提交", "expected": "提示密码错误"},
]


def make_client(user):
    """带认证的 API Client。

    必须带 User-Agent：AuditService 写 user_agent 时对缺失 UA 的请求会写入 None，
    而 audit_auditlog.user_agent 非空（common/* 建议修复，见交付报告）。
    """
    client = APIClient(HTTP_USER_AGENT="nanoqa-tests")
    client.force_authenticate(user)
    return client


def make_user(username="admin"):
    return User.objects.create(
        username=username, is_superuser=True, is_staff=True, is_system_admin=True
    )


def make_project(user, key="SHOP"):
    organization = Organization.objects.create(name=f"组织{key}", slug=key.lower(), owner=user)
    return Project.objects.create(
        organization=organization, name="商城项目", key=key, owner=user
    )


def make_case(project, key, title="登录校验", priority="P1", versions=1):
    case = TestCase.objects.create(
        organization=project.organization,
        project=project,
        case_key=key,
        title=title,
        priority=priority,
        creator=project.owner,
        current_version=versions,
    )
    for version in range(1, versions + 1):
        TestCaseVersion.objects.create(
            test_case=case,
            version=version,
            title=title,
            steps=STEPS,
            expected_result="登录被拒绝",
            created_by=project.owner,
            change_summary=f"v{version}",
        )
    return case


def make_plan(project, name="回归测试计划", status=TestPlan.STATUS_DRAFT, cases=()):
    plan = TestPlan.objects.create(
        organization=project.organization,
        project=project,
        name=name,
        status=status,
        created_by=project.owner,
    )
    for case in cases:
        TestPlanCase.objects.create(
            test_plan=plan, test_case=case, priority=case.priority, execution_status="not_run"
        )
    return plan
