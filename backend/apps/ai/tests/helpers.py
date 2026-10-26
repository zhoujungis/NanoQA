"""AI 测试数据构造。"""
from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.projects.models import Project
from apps.projects.services.keys import next_key
from apps.testcases.models import TestCase, TestCaseVersion


def make_user(username: str = "qa") -> User:
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password="pwd", is_system_admin=True
    )


def make_project(user: User, key: str = "SHOP") -> Project:
    org = Organization.objects.create(name="演示组织", slug=f"org-{key.lower()}", owner=user)
    return Project.objects.create(organization=org, name="商城项目", key=key, owner=user)


def make_case(project: Project, user: User, title: str = "默认用例", steps=None,
              expected_result: str = "符合预期", precondition: str = "用户已登录") -> TestCase:
    case = TestCase.objects.create(
        organization=project.organization, project=project, case_key=next_key(project, "TC"),
        title=title, creator=user, status=TestCase.STATUS_DRAFT,
    )
    TestCaseVersion.objects.create(
        test_case=case, version=1, title=title, precondition=precondition,
        steps=steps if steps is not None else [{"order": 1, "action": "打开页面", "expected": "加载成功"}],
        expected_result=expected_result, created_by=user,
    )
    return case


def fake_cases(count: int = 3) -> list[dict]:
    return [
        {
            "title": f"AI 生成用例{i}",
            "priority": "P1",
            "type": "functional",
            "precondition": "用户已登录",
            "steps": [
                {"action": f"执行步骤{i}-1", "expected": "预期结果{i}-1"},
                {"action": f"执行步骤{i}-2", "expected": "预期结果{i}-2"},
            ],
            "expected_result": f"用例{i}通过",
        }
        for i in range(1, count + 1)
    ]
