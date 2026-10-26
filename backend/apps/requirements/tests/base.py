"""测试公共固定装置：组织/项目/用户/角色 + 用例/结果工厂 + envelope 断言。"""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.accounts.tests.helpers import ensure_rbac_seed
from apps.defects.models import Defect
from apps.executions.models import TestResult, TestRun
from apps.organizations.models import Organization
from apps.projects.models import Project, ProjectMember
from apps.requirements.models import Requirement
from apps.testcases.models import TestCase as TestCaseModel, TestCaseVersion
from apps.testplans.models import TestPlan


class NanoAPITestCase(TestCase):
    """API 测试基类（Django 原生 runner）。"""

    @classmethod
    def setUpTestData(cls):
        cache.clear()
        ensure_rbac_seed()  # 防御：TransactionTestCase flush 后种子可能被截断
        cls.owner = User.objects.create_user(username="owner", password="pw")
        cls.org = Organization.objects.create(name="质量中心", slug="qa-center", owner=cls.owner)
        cls.project = Project.objects.create(
            organization=cls.org, name="商城项目", key="SHOP", owner=cls.owner
        )
        cls.sysadmin = User.objects.create_user(username="sysadmin", password="pw", is_system_admin=True)
        cls.manager = User.objects.create_user(username="manager", password="pw")
        cls.qa = User.objects.create_user(username="qa", password="pw")
        cls.viewer = User.objects.create_user(username="viewer", password="pw")
        cls.outsider = User.objects.create_user(username="outsider", password="pw")
        for user, role_code in ((cls.manager, "admin"), (cls.qa, "qa"), (cls.viewer, "viewer")):
            ProjectMember.objects.create(
                project=cls.project, user=user, role=Role.objects.get(code=role_code)
            )

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self._case_seq = 0
        self._req_seq = 0
        self._bug_seq = 0

    # ---------------------------------------------------------------- 工具
    def login(self, user):
        self.client.force_authenticate(user=user)
        return self.client

    def assertCode(self, response, code, http_status=None):
        """断言 envelope 业务码，返回 data。"""
        if http_status is not None:
            self.assertEqual(response.status_code, http_status, msg=str(response.content))
        body = response.json()
        self.assertEqual(body["code"], code, msg=str(response.content))
        return body["data"]

    def make_testcase(self, **kw):
        self._case_seq += 1
        defaults = {
            "organization": self.org,
            "project": self.project,
            "case_key": f"TC-FIX-{self._case_seq:06d}",
            "title": f"固定用例-{self._case_seq}",
            "creator": self.owner,
        }
        defaults.update(kw)
        return TestCaseModel.objects.create(**defaults)

    def make_requirement(self, **kw):
        self._req_seq += 1
        defaults = {
            "organization": self.org,
            "project": self.project,
            "key": f"REQ-FIX-{self._req_seq:06d}",
            "title": f"固定需求-{self._req_seq}",
            "creator": self.owner,
        }
        defaults.update(kw)
        return Requirement.objects.create(**defaults)

    def make_defect(self, **kw):
        self._bug_seq += 1
        defaults = {
            "organization": self.org,
            "project": self.project,
            "key": f"BUG-FIX-{self._bug_seq:06d}",
            "title": f"固定缺陷-{self._bug_seq}",
            "reporter": self.owner,
        }
        defaults.update(kw)
        return Defect.objects.create(**defaults)

    def make_run(self, name="run"):
        plan = TestPlan.objects.create(
            organization=self.org, project=self.project, name=f"plan-{name}", created_by=self.owner
        )
        return TestRun.objects.create(
            organization=self.org, project=self.project, test_plan=plan, name=name, created_by=self.owner
        )

    def make_result(self, run, case, status):
        version, _ = TestCaseVersion.objects.get_or_create(
            test_case=case,
            version=case.current_version,
            defaults={"title": case.title, "steps": [], "created_by": self.owner},
        )
        return TestResult.objects.create(
            test_run=run, test_case=case, test_case_version=version, status=status
        )
