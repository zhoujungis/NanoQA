"""测试基类：组织/项目/模块/标签夹具 + 超级管理员（全权限）+ 通用载荷。"""
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.projects.models import Module, Project, Tag


class NanoTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pass12345"
        )
        cls.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="pass12345"
        )
        cls.org = Organization.objects.create(name="Nano Org", slug="nano-org", owner=cls.user)
        cls.project = Project.objects.create(
            organization=cls.org, name="Shop", key="SHOP", owner=cls.user
        )
        cls.root_module = Module.objects.create(project=cls.project, name="Auth")
        cls.module = Module.objects.create(project=cls.project, name="Login", parent=cls.root_module)
        cls.child_module = Module.objects.create(project=cls.project, name="Password", parent=cls.module)
        cls.tag_smoke = Tag.objects.create(project=cls.project, name="smoke")
        cls.tag_fast = Tag.objects.create(project=cls.project, name="fast")

    def setUp(self):
        self.client.force_authenticate(self.user)
        # AuditService 落库 user_agent NOT NULL，测试请求统一携带 UA（见报告：audit 服务容错建议）
        self.client.credentials(HTTP_USER_AGENT="nanoqa-tests")

    # ---- helpers ----
    def payload(self, **overrides) -> dict:
        data = {
            "title": "登录成功",
            "priority": "P1",
            "steps": [{"action": "打开登录页", "expected": "登录页正常展示"}],
        }
        data.update(overrides)
        return data

    @property
    def list_url(self) -> str:
        return f"/api/v1/projects/{self.project.id}/testcases/"

    def detail_url(self, case_id) -> str:
        return f"/api/v1/testcases/{case_id}/"

    def create_case(self, **overrides) -> dict:
        response = self.client.post(self.list_url, self.payload(**overrides), format="json")
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["code"], 0)
        return body["data"]

    def patch_case(self, case_id, data: dict):
        return self.client.patch(self.detail_url(case_id), data, format="json")

    def list_cases(self, **params) -> dict:
        response = self.client.get(self.list_url, params)
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["code"], 0)
        return body["data"]
