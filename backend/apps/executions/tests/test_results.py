"""结果提交测试：P/F/B/S 同步、覆盖式重复提交 + 审计、批量原子性、PATCH 修改。"""
from django.core.cache import cache
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.executions.models import TestResult
from apps.testplans.models import TestPlanCase
from apps.testplans.tests.factories import make_case, make_client, make_plan, make_project, make_user


class TestResultSubmitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.project = make_project(cls.user)
        cls.case1 = make_case(cls.project, "SHOP-TC-000001", title="登录-正确密码", priority="P0")
        cls.case2 = make_case(cls.project, "SHOP-TC-000002", title="登录-错误密码")
        cls.case3 = make_case(cls.project, "SHOP-TC-000003", title="登录-锁定")
        cls.plan = make_plan(cls.project, cases=[cls.case1, cls.case2, cls.case3])

    def setUp(self):
        cache.clear()
        self.client = make_client(self.user)

    def _start_run(self):
        resp = self.client.post(f"/api/v1/testplans/{self.plan.pk}/start/", {}, format="json")
        self.assertEqual(resp.status_code, 201)
        return resp.json()["data"]

    def _submit(self, run_id, payload):
        return self.client.post(f"/api/v1/runs/{run_id}/results/", payload, format="json")

    def test_submit_pass_updates_plan_case_and_audit(self):
        run = self._start_run()
        resp = self._submit(
            run["id"],
            {"test_case_id": self.case1.pk, "status": "passed", "actual_result": "登录成功", "duration": 120},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertEqual(data["status"], "passed")

        result = TestResult.objects.get(pk=data["id"])
        self.assertEqual(result.executed_by, self.user)
        self.assertIsNotNone(result.executed_at)
        self.assertEqual(result.duration, 120)

        link = TestPlanCase.objects.get(test_plan=self.plan, test_case=self.case1)
        self.assertEqual(link.execution_status, "passed")
        self.assertTrue(
            AuditLog.objects.filter(
                action="execute", object_type="testresult", object_id=result.pk
            ).exists()
        )

    def test_submit_fail_block_skip_sync_plan_case(self):
        run = self._start_run()
        for case, status_value in [
            (self.case1, "failed"),
            (self.case2, "blocked"),
            (self.case3, "skipped"),
        ]:
            resp = self._submit(run["id"], {"test_case_id": case.pk, "status": status_value})
            self.assertEqual(resp.status_code, 201)
            self.assertEqual(resp.json()["data"]["status"], status_value)
            link = TestPlanCase.objects.get(test_plan=self.plan, test_case=case)
            self.assertEqual(link.execution_status, status_value)

    def test_resubmit_overwrites_and_audits_both_statuses(self):
        run = self._start_run()
        self._submit(run["id"], {"test_case_id": self.case1.pk, "status": "passed"})
        resp = self._submit(
            run["id"],
            {"test_case_id": self.case1.pk, "status": "failed", "actual_result": "接口返回 500"},
        )
        self.assertEqual(resp.status_code, 201)

        result = TestResult.objects.get(test_run_id=run["id"], test_case=self.case1)
        self.assertEqual(result.status, "failed")  # 覆盖式更新（D3a）
        self.assertEqual(result.actual_result, "接口返回 500")
        self.assertEqual(
            TestResult.objects.filter(test_run_id=run["id"], test_case=self.case1).count(), 1
        )

        audit = (
            AuditLog.objects.filter(action="execute", object_type="testresult", object_id=result.pk)
            .order_by("-id")
            .first()
        )
        self.assertEqual(audit.old_data["status"], "passed")
        self.assertEqual(audit.new_data["status"], "failed")

    def test_submit_unknown_case_returns_40005(self):
        run = self._start_run()
        resp = self._submit(run["id"], {"test_case_id": 999999, "status": "passed"})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], 40005)

    def test_bulk_submit_is_atomic(self):
        run = self._start_run()
        resp = self.client.post(
            f"/api/v1/runs/{run['id']}/results/bulk/",
            {"items": [
                {"test_case_id": self.case1.pk, "status": "passed"},
                {"test_case_id": self.case2.pk, "status": "failed", "comment": "回归失败"},
            ]},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["data"]["total"], 2)
        self.assertEqual(TestResult.objects.filter(test_run_id=run["id"], status="passed").count(), 1)

        resp = self.client.post(
            f"/api/v1/runs/{run['id']}/results/bulk/",
            {"items": [
                {"test_case_id": self.case3.pk, "status": "skipped"},
                {"test_case_id": 999999, "status": "passed"},
            ]},
            format="json",
        )
        self.assertEqual(resp.json()["code"], 40005)
        result3 = TestResult.objects.get(test_run_id=run["id"], test_case=self.case3)
        self.assertEqual(result3.status, "not_run")  # 整批回滚

    def test_patch_result_updates_and_audits(self):
        run = self._start_run()
        result = TestResult.objects.get(test_run_id=run["id"], test_case=self.case1)
        resp = self.client.patch(
            f"/api/v1/results/{result.pk}/",
            {"status": "blocked", "comment": "测试环境不可用"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        result.refresh_from_db()
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.comment, "测试环境不可用")
        link = TestPlanCase.objects.get(test_plan=self.plan, test_case=self.case1)
        self.assertEqual(link.execution_status, "blocked")
        self.assertTrue(
            AuditLog.objects.filter(action="update", object_type="testresult", object_id=result.pk).exists()
        )
