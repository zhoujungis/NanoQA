"""FAIL→缺陷事务测试（§34）：Defect + TestResultDefect + TestCaseDefect 同事务落库。"""
from django.core.cache import cache
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.defects.models import Defect, TestCaseDefect, TestResultDefect
from apps.executions.models import TestResult
from apps.testplans.tests.factories import make_case, make_client, make_plan, make_project, make_user


class ResultDefectTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.project = make_project(cls.user)
        cls.case = make_case(cls.project, "SHOP-TC-000001", title="登录-错误密码", versions=2)
        cls.plan = make_plan(cls.project, cases=[cls.case])

    def setUp(self):
        cache.clear()
        self.client = make_client(self.user)

    def _run_and_result(self, status="failed", actual_result="接口返回 500"):
        resp = self.client.post(
            f"/api/v1/testplans/{self.plan.pk}/start/",
            {"environment": "Staging", "build_version": "2.8.1"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        run = resp.json()["data"]
        self.client.post(
            f"/api/v1/runs/{run['id']}/results/",
            {"test_case_id": self.case.pk, "status": status, "actual_result": actual_result},
            format="json",
        )
        return TestResult.objects.get(test_run_id=run["id"], test_case=self.case)

    def test_create_defect_from_failed_result(self):
        result = self._run_and_result()
        resp = self.client.post(f"/api/v1/results/{result.pk}/defects/", {}, format="json")
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertIsNone(data["warning"])
        defect_data = data["defect"]
        self.assertEqual(defect_data["key"], "SHOP-BUG-000001")

        defect = Defect.objects.get(pk=defect_data["id"])
        self.assertEqual(defect.reporter, self.user)
        self.assertEqual(defect.status, Defect.STATUS_OPEN)
        self.assertEqual(defect.title, f"[失败] {self.case.case_key} {self.case.title}")
        self.assertEqual(defect.environment, "Staging")  # 默认取 run 环境/版本
        self.assertEqual(defect.version, "2.8.1")
        self.assertIn("打开登录页", defect.description)  # 步骤快照
        self.assertIn("接口返回 500", defect.description)  # actual_result

        self.assertTrue(TestResultDefect.objects.filter(test_result=result, defect=defect).exists())
        self.assertTrue(TestCaseDefect.objects.filter(test_case=self.case, defect=defect).exists())
        self.assertTrue(
            AuditLog.objects.filter(action="create", object_type="defect", object_id=defect.pk).exists()
        )

    def test_defect_with_custom_fields_and_incrementing_key(self):
        result = self._run_and_result()
        resp = self.client.post(
            f"/api/v1/results/{result.pk}/defects/",
            {"title": "登录接口 500", "severity": "Critical", "priority": "P0", "comment": "稳定复现"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        defect = Defect.objects.get(key="SHOP-BUG-000001")
        self.assertEqual(defect.title, "登录接口 500")
        self.assertEqual(defect.severity, "Critical")
        self.assertEqual(defect.priority, "P0")
        self.assertIn("稳定复现", defect.description)

        resp = self.client.post(f"/api/v1/results/{result.pk}/defects/", {}, format="json")
        self.assertEqual(resp.json()["data"]["defect"]["key"], "SHOP-BUG-000002")  # 编号单调递增

    def test_non_failed_result_warns_but_creates(self):
        result = self._run_and_result(status="passed", actual_result="登录成功")
        resp = self.client.post(f"/api/v1/results/{result.pk}/defects/", {}, format="json")
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertIsNotNone(data["warning"])  # 非 failed 给提示但不拦截
        self.assertEqual(Defect.objects.count(), 1)
        self.assertTrue(TestResultDefect.objects.filter(test_result=result).exists())
        self.assertTrue(TestCaseDefect.objects.filter(test_case=self.case).exists())
