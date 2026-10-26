"""测试计划 API 测试：状态机 40004、乐观锁 40003、start 事务、无用例 40007。"""
from django.core.cache import cache
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.executions.models import TestResult, TestRun
from apps.testplans.models import TestPlan, TestPlanCase
from apps.testplans.tests.factories import make_case, make_client, make_plan, make_project, make_user


class TestPlanApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.project = make_project(cls.user)
        cls.case1 = make_case(cls.project, "SHOP-TC-000001", title="登录-正确密码", priority="P0", versions=2)
        cls.case2 = make_case(cls.project, "SHOP-TC-000002", title="登录-错误密码", priority="P2")
        cls.plan = make_plan(cls.project)

    def setUp(self):
        cache.clear()
        self.client = make_client(self.user)

    def _url(self, suffix=""):
        return f"/api/v1/testplans/{self.plan.pk}{suffix}"

    # ---------------------------------------------------------------- 基础 CRUD

    def test_create_plan_sets_org_creator_and_audits(self):
        resp = self.client.post(
            f"/api/v1/projects/{self.project.pk}/testplans/",
            {"name": "2.8.1 回归计划", "version": "2.8.1", "owner_id": self.user.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        plan = TestPlan.objects.get(pk=data["id"])
        self.assertEqual(plan.organization, self.project.organization)
        self.assertEqual(plan.created_by, self.user)
        self.assertEqual(plan.owner, self.user)
        self.assertEqual(plan.status, TestPlan.STATUS_DRAFT)
        self.assertTrue(
            AuditLog.objects.filter(action="create", object_type="testplan", object_id=plan.pk).exists()
        )

    def test_illegal_status_transition_returns_40004(self):
        resp = self.client.patch(
            self._url("/"),
            {"status": "completed", "updated_at": self.plan.updated_at.isoformat()},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40004)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, TestPlan.STATUS_DRAFT)

    def test_status_transition_and_optimistic_lock(self):
        resp = self.client.patch(
            self._url("/"),
            {"status": "ready", "updated_at": self.plan.updated_at.isoformat()},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, TestPlan.STATUS_READY)
        self.assertTrue(
            AuditLog.objects.filter(
                action="transition", object_type="testplan", object_id=self.plan.pk
            ).exists()
        )

        stale = self.plan.updated_at.isoformat()
        self.client.patch(self._url("/"), {"name": "改名", "updated_at": stale}, format="json")
        resp = self.client.patch(self._url("/"), {"name": "再改", "updated_at": stale}, format="json")
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["code"], 40003)

    def test_delete_plan_cancels_without_physical_delete(self):
        resp = self.client.delete(self._url("/"))
        self.assertEqual(resp.status_code, 200)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, TestPlan.STATUS_CANCELLED)
        self.assertTrue(TestPlan.objects.filter(pk=self.plan.pk).exists())
        self.assertTrue(
            AuditLog.objects.filter(action="delete", object_type="testplan", object_id=self.plan.pk).exists()
        )

    # ---------------------------------------------------------------- 计划用例

    def test_add_cases_skips_existing_and_copies_priority(self):
        url = self._url("/cases/")
        resp = self.client.post(url, {"test_case_ids": [self.case1.pk, self.case2.pk]}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["data"]["added"], [self.case1.pk, self.case2.pk])

        resp = self.client.post(url, {"test_case_ids": [self.case1.pk, self.case2.pk]}, format="json")
        self.assertEqual(resp.json()["data"]["skipped"], [self.case1.pk, self.case2.pk])
        self.assertEqual(TestPlanCase.objects.filter(test_plan=self.plan).count(), 2)

        link = TestPlanCase.objects.get(test_plan=self.plan, test_case=self.case1)
        self.assertEqual(link.priority, "P0")
        self.assertEqual(link.execution_status, "not_run")

    def test_update_and_remove_plan_case(self):
        self.client.post(self._url("/cases/"), {"test_case_ids": [self.case1.pk]}, format="json")
        resp = self.client.patch(
            self._url(f"/cases/{self.case1.pk}/"),
            {"priority": "P3", "assigned_to": self.user.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        link = TestPlanCase.objects.get(test_plan=self.plan, test_case=self.case1)
        self.assertEqual(link.priority, "P3")
        self.assertEqual(link.assigned_to, self.user)

        resp = self.client.delete(self._url(f"/cases/{self.case1.pk}/"))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(TestPlanCase.objects.filter(test_plan=self.plan).exists())

    # ---------------------------------------------------------------- start

    def test_start_creates_run_with_results_and_version_snapshot(self):
        self.client.post(
            self._url("/cases/"), {"test_case_ids": [self.case1.pk, self.case2.pk]}, format="json"
        )
        resp = self.client.post(
            self._url("/start/"),
            {"environment": "Staging", "build_version": "2.8.1"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertEqual(data["status"], "running")

        run = TestRun.objects.get(pk=data["id"])
        self.assertEqual(run.test_plan, self.plan)
        self.assertEqual(run.created_by, self.user)
        self.assertEqual(run.environment, "Staging")
        self.assertIsNotNone(run.started_at)

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, TestPlan.STATUS_RUNNING)

        results = TestResult.objects.filter(test_run=run)
        self.assertEqual(results.count(), 2)  # 结果条数 = 计划用例数
        snapshot = results.get(test_case=self.case1)
        self.assertEqual(snapshot.test_case_version.version, 2)  # 绑定当前版本快照
        self.assertEqual(snapshot.status, "not_run")
        self.assertEqual(
            results.get(test_case=self.case2).test_case_version.version, 1
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action="transition", object_type="testplan", object_id=self.plan.pk
            ).exists()
        )

    def test_start_without_cases_returns_40007(self):
        resp = self.client.post(self._url("/start/"), {}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40007)
        self.assertEqual(TestRun.objects.count(), 0)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, TestPlan.STATUS_DRAFT)

    def test_start_twice_returns_40007(self):
        self.client.post(self._url("/cases/"), {"test_case_ids": [self.case1.pk]}, format="json")
        self.client.post(self._url("/start/"), {}, format="json")
        resp = self.client.post(self._url("/start/"), {}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40007)
        self.assertEqual(TestRun.objects.count(), 1)
