"""测试工具：用户 / 组织 / 项目 / 成员绑定构造。"""
from importlib import import_module

from django.apps import apps as django_apps
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.organizations.models import Organization, OrganizationMember
from apps.projects.models import Project, ProjectMember


def ensure_rbac_seed() -> None:
    """幂等补种权限/角色种子。

    TransactionTestCase 的 flush 会截断数据迁移种子（Role/Permission），
    测试基座在使用角色前自愈，保证任意测试顺序下都可用。
    """
    import_module("apps.accounts.migrations.0003_seed_permissions_roles").seed(django_apps, None)


class NanoAPITestCase(APITestCase):
    """公共基类：清缓存（权限缓存 / 限流计数），保证用例隔离。"""

    def setUp(self):
        cache.clear()
        ensure_rbac_seed()
        # AuditLog.user_agent 非空约束；测试客户端默认不带 User-Agent
        self.client.defaults["HTTP_USER_AGENT"] = "NanoQA-Test-Client"


def create_user(username: str, password: str = "pass1234", **kwargs) -> User:
    return User.objects.create_user(
        username=username,
        password=password,
        email=kwargs.pop("email", f"{username}@example.com"),
        **kwargs,
    )


def role(code: str) -> Role:
    try:
        return Role.objects.get(code=code)
    except Role.DoesNotExist:
        ensure_rbac_seed()
        return Role.objects.get(code=code)


def make_org(owner: User, slug: str, name: str = "测试组织") -> Organization:
    org = Organization.objects.create(name=name, slug=slug, owner=owner)
    OrganizationMember.objects.create(organization=org, user=owner, role=role("admin"))
    return org


def bind_org(user: User, org: Organization, role_code: str) -> OrganizationMember:
    member, _ = OrganizationMember.objects.get_or_create(
        organization=org, user=user, defaults={"role": role(role_code)}
    )
    return member


def make_project(org: Organization, owner: User, key: str, name: str = "示例项目") -> Project:
    project = Project.objects.create(organization=org, name=name, key=key, owner=owner)
    ProjectMember.objects.create(project=project, user=owner, role=role("admin"))
    return project


def bind_project(user: User, project: Project, role_code: str) -> ProjectMember:
    member, _ = ProjectMember.objects.get_or_create(
        project=project, user=user, defaults={"role": role(role_code)}
    )
    return member
