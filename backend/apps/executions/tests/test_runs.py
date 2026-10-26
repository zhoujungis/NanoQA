"""TestRun API 测试：run 详情统计、再开一轮、结果列表筛选。"""
from django.core.cache import cache
from django.test import TestCase

from apps.executions.models import TestResult
from apps.testplans.models import TestPlan
from apps.testplans.tests.factories import make_case, make_client, make_plan, make_project, make_user


class TestRunApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.project = make_project(cls.user)
        cls.case1 = make_case(cls.project, "SHOP-TC-000001", title="登录-正确密码", versions=2)
        cls.case2 = make_case(cls.project, "SHOP-TC-000002", title="登录-错误密码")
        cls.plan = make_plan(cls.project, cases=[cls.case1, cls.case2])

    def setUp(self):
        cache.clear()
        self.client = make_client(self.user)

    def _start(self, name="第一轮"):
        resp = self.client.post(
            f"/api/v1/testplans/{self.plan.pk}/start/", {"name": name}, format="json"
        )
        self.assertEqual(resp.status_code, 201)
        return resp.json()["data"]

    def test_run_detail_contains_stats(self):
        run = self._start()
        resp = self.client.get(f"/api/v1/runs/{run['id']}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["name"], "第一轮")
        self.assertEqual(data["stats"]["total"], 2)
        self.assertEqual(data["stats"]["not_run"], 2)
        self.assertEqual(data["stats"]["passed"], 0)

    def test_list_runs_and_create_second_run(self):
        first = self._start()
        resp = self.client.get(f"/api/v1/testplans/{self.plan.pk}/runs/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["total"], 1)

        resp = self.client.post(
            f"/api/v1/testplans/{self.plan.pk}/runs/",
            {"name": "第二轮", "environment": "Prod", "build_version": "2.8.2"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        second = resp.json()["data"]
        self.assertNotEqual(second["id"], first["id"])
        self.assertEqual(second["stats"]["not_run"], 2)  # 同样预建 not_run 结果
        self.assertEqual(TestResult.objects.filter(test_run_id=second["id"]).count(), 2)
        result = TestResult.objects.get(test_run_id=second["id"], test_case=self.case1)
        self.assertEqual(result.test_case_version.version, 2)  # 版本快照绑定
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, TestPlan.STATUS_RUNNING)

    def test_create_run_requires_running_or_completed_plan(self):
        resp = self.client.post(f"/api/v1/testplans/{self.plan.pk}/runs/", {}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40007)

    def test_results_list_filters(self):
        run = self._start()
        self.client.post(
            f"/api/v1/runs/{run['id']}/results/",
            {"test_case_id": self.case1.pk, "status": "passed"},
            format="json",
        )
        resp = self.client.get(f"/api/v1/runs/{run['id']}/results/?status=passed")
        data = resp.json()["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["case_key"], "SHOP-TC-000001")
        self.assertEqual(data["items"][0]["case_version"], 2)

        resp = self.client.get(f"/api/v1/runs/{run['id']}/results/?status=not_run")
        self.assertEqual(resp.json()["data"]["total"], 1)

        resp = self.client.get(f"/api/v1/runs/{run['id']}/results/?q=000002")
        data = resp.json()["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["case_key"], "SHOP-TC-000002")
