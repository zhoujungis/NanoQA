"""Dashboard 口径单测（§35）：not_run 不进 pass_rate 分母。"""
from rest_framework.test import APITestCase

from apps.reports.tests import helpers


class DashboardMetricsTests(APITestCase):
    def setUp(self):
        self.user = helpers.make_user()
        self.project = helpers.make_project(self.user)
        self.client.force_authenticate(self.user)

    def _dashboard(self):
        response = self.client.get(f"/api/v1/projects/{self.project.id}/dashboard/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["code"], 0)
        return body["data"]

    def test_pass_rate_excludes_not_run(self):
        """3 passed + 2 failed + 5 not_run → pass_rate=3/5=60%，execution_rate=5/10=50%。"""
        _plan, run = helpers.make_plan_and_run(self.project, self.user)
        cases = [helpers.make_case(self.project, self.user, title=f"用例{i}") for i in range(10)]
        for case in cases[:3]:
            helpers.make_result(run, case, "passed", self.user)
        for case in cases[3:5]:
            helpers.make_result(run, case, "failed", self.user)
        for case in cases[5:]:
            helpers.make_result(run, case, "not_run", self.user)

        execution = self._dashboard()["execution"]
        self.assertEqual(execution["executed"], 5)
        self.assertEqual(execution["not_run"], 5)
        self.assertEqual(execution["passed"], 3)
        self.assertEqual(execution["failed"], 2)
        self.assertEqual(execution["execution_rate"], 0.5)
        self.assertEqual(execution["pass_rate"], 0.6)
        self.assertEqual(execution["failure_rate"], 0.4)
        self.assertEqual(execution["block_rate"], 0.0)

    def test_cases_without_results_count_as_not_run(self):
        _plan, run = helpers.make_plan_and_run(self.project, self.user)
        passed_case = helpers.make_case(self.project, self.user, title="通过用例")
        helpers.make_case(self.project, self.user, title="未执行用例1")
        helpers.make_case(self.project, self.user, title="未执行用例2")
        helpers.make_result(run, passed_case, "passed", self.user)

        data = self._dashboard()
        self.assertEqual(data["total_cases"], 3)
        self.assertEqual(data["execution"]["executed"], 1)
        self.assertEqual(data["execution"]["not_run"], 2)
        self.assertEqual(data["execution"]["pass_rate"], 1.0)

    def test_cases_by_status_and_priority(self):
        helpers.make_case(self.project, self.user, title="P0 用例", priority="P0")
        helpers.make_case(self.project, self.user, title="P1 用例", priority="P1")
        helpers.make_case(self.project, self.user, title="P1 用例2", priority="P1")

        data = self._dashboard()
        self.assertEqual(data["total_cases"], 3)
        self.assertEqual(data["cases_by_status"]["active"], 3)
        self.assertEqual(data["cases_by_priority"], {"P0": 1, "P1": 2})

    def test_defects_stats(self):
        helpers.make_defect(self.project, self.user, title="打开缺陷", severity="Blocker", status="Open")
        helpers.make_defect(self.project, self.user, title="处理中缺陷", severity="Major", status="In Progress")
        helpers.make_defect(self.project, self.user, title="已关闭缺陷", severity="Minor", status="Closed")

        defects = self._dashboard()["defects"]
        self.assertEqual(defects["total"], 3)
        self.assertEqual(defects["open"], 1)
        self.assertEqual(defects["in_progress"], 1)
        self.assertEqual(defects["closed"], 1)
        self.assertEqual(defects["resolved"], 0)
        self.assertEqual(defects["by_severity"], {"Blocker": 1, "Major": 1, "Minor": 1})

    def test_requirement_coverage(self):
        helpers.make_requirement(self.project, self.user, title="已覆盖需求", covered=True)
        helpers.make_requirement(self.project, self.user, title="未覆盖需求")
        helpers.make_requirement(self.project, self.user, title="未覆盖需求2")

        coverage = self._dashboard()["requirement_coverage"]
        self.assertEqual(coverage["total"], 3)
        self.assertEqual(coverage["covered"], 1)
        self.assertEqual(coverage["rate"], round(1 / 3, 4))

    def test_recent_failures_limited_to_10_and_recent_plans_to_5(self):
        _plan, run = helpers.make_plan_and_run(self.project, self.user)
        for index in range(12):
            case = helpers.make_case(self.project, self.user, title=f"失败用例{index}")
            helpers.make_result(run, case, "failed", self.user)
        for index in range(7):
            helpers.make_plan_and_run(self.project, self.user, name=f"计划{index}")

        data = self._dashboard()
        self.assertEqual(len(data["recent_failures"]), 10)
        self.assertEqual(len(data["recent_plans"]), 5)
        self.assertIn("case_key", data["recent_failures"][0])
        self.assertIn("title", data["recent_failures"][0])
        self.assertIn("executed_at", data["recent_failures"][0])
        self.assertIn("name", data["recent_plans"][0])
        self.assertIn("status", data["recent_plans"][0])
        self.assertIn("updated_at", data["recent_plans"][0])

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(f"/api/v1/projects/{self.project.id}/dashboard/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], 40002)
