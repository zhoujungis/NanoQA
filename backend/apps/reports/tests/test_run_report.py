"""Run 报告单测（§36）：模块聚合 / 版本快照标题 / 失败用例缺陷 / 历史报告列表。"""
from rest_framework.test import APITestCase

from apps.testcases.models import TestCaseVersion
from apps.reports.tests import helpers


class RunReportTests(APITestCase):
    def setUp(self):
        self.user = helpers.make_user()
        self.project = helpers.make_project(self.user)
        self.client.force_authenticate(self.user)

    def _report(self, run):
        response = self.client.get(f"/api/v1/runs/{run.id}/report/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["code"], 0)
        return body["data"]

    def test_overview_and_module_analysis(self):
        login_module = helpers.make_module(self.project, "登录")
        _plan, run = helpers.make_plan_and_run(self.project, self.user)
        case_a = helpers.make_case(self.project, self.user, title="登录成功", module=login_module)
        case_b = helpers.make_case(self.project, self.user, title="登录失败", module=login_module)
        case_c = helpers.make_case(self.project, self.user, title="登录超时", module=login_module)
        case_d = helpers.make_case(self.project, self.user, title="根模块用例")  # module=null

        helpers.make_result(run, case_a, "passed", self.user)
        helpers.make_result(run, case_b, "failed", self.user)
        helpers.make_result(run, case_c, "not_run", self.user)
        helpers.make_result(run, case_d, "passed", self.user)

        data = self._report(run)
        overview = data["overview"]
        self.assertEqual(overview["total"], 4)
        self.assertEqual(overview["passed"], 2)
        self.assertEqual(overview["failed"], 1)
        self.assertEqual(overview["blocked"], 0)
        self.assertEqual(overview["skipped"], 0)
        self.assertEqual(overview["pass_rate"], round(2 / 3, 4))  # not_run 不进分母

        modules = {row["module_name"]: row for row in data["module_analysis"]}
        self.assertEqual(set(modules), {"登录", "未分类"})
        self.assertEqual(modules["登录"]["total"], 3)
        self.assertEqual(modules["登录"]["passed"], 1)
        self.assertEqual(modules["登录"]["pass_rate"], 0.5)  # 1 passed / 2 executed
        self.assertEqual(modules["未分类"]["total"], 1)
        self.assertEqual(modules["未分类"]["pass_rate"], 1.0)
        self.assertIsNone(modules["未分类"]["module_id"])

        self.assertEqual(data["environment"], run.environment)
        self.assertEqual(data["build_version"], run.build_version)
        self.assertIsNotNone(data["started_at"])

    def test_failed_cases_use_version_snapshot_title(self):
        login_module = helpers.make_module(self.project, "登录")
        _plan, run = helpers.make_plan_and_run(self.project, self.user)
        case = helpers.make_case(self.project, self.user, title="旧标题", module=login_module)
        helpers.make_result(run, case, "failed", self.user)

        # 用例后续改名并出 v2，报告仍按执行时版本快照渲染（坑 4）
        TestCaseVersion.objects.create(
            test_case=case, version=2, title="新标题",
            steps=[{"order": 1, "action": "新步骤", "expected": "新预期"}], created_by=self.user,
        )
        case.title = "新标题"
        case.save(update_fields=["title"])

        data = self._report(run)
        self.assertEqual(len(data["failed_cases"]), 1)
        failed = data["failed_cases"][0]
        self.assertEqual(failed["title"], "旧标题")
        self.assertEqual(failed["case_key"], case.case_key)
        self.assertEqual(failed["module"], "登录")
        self.assertEqual(failed["executor"], self.user.username)
        self.assertIsNotNone(failed["executed_at"])
        self.assertEqual(failed["defects"], [])

    def test_failed_cases_with_defects_and_defect_stats(self):
        _plan, run = helpers.make_plan_and_run(self.project, self.user)
        case = helpers.make_case(self.project, self.user, title="结算失败")
        result = helpers.make_result(run, case, "failed", self.user)
        defect = helpers.make_defect(self.project, self.user, title="结算金额错误", severity="Critical", status="Open")
        helpers.link_result_defect(result, defect)

        data = self._report(run)
        self.assertEqual(data["failed_cases"][0]["defects"], [
            {"key": defect.key, "title": "结算金额错误", "status": "Open"},
        ])
        defect_stats = data["defect_stats"]
        self.assertEqual(defect_stats["total"], 1)
        self.assertEqual(defect_stats["open"], 1)
        self.assertEqual(defect_stats["by_severity"], {"Critical": 1})

    def test_reports_list_with_pass_rate(self):
        _plan, run1 = helpers.make_plan_and_run(self.project, self.user, name="计划一")
        case_a = helpers.make_case(self.project, self.user, title="用例A")
        case_b = helpers.make_case(self.project, self.user, title="用例B")
        helpers.make_result(run1, case_a, "passed", self.user)
        helpers.make_result(run1, case_b, "failed", self.user)

        _plan2, run2 = helpers.make_plan_and_run(self.project, self.user, name="计划二")
        case_c = helpers.make_case(self.project, self.user, title="用例C")
        helpers.make_result(run2, case_c, "not_run", self.user)

        response = self.client.get(f"/api/v1/projects/{self.project.id}/reports/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["items"]), 2)
        by_run = {item["run_id"]: item for item in data["items"]}
        self.assertEqual(by_run[run1.id]["total"], 2)
        self.assertEqual(by_run[run1.id]["passed"], 1)
        self.assertEqual(by_run[run1.id]["pass_rate"], 0.5)
        self.assertEqual(by_run[run2.id]["total"], 1)
        self.assertEqual(by_run[run2.id]["pass_rate"], 0.0)  # 全 not_run 不进分母
        self.assertEqual(by_run[run1.id]["name"], "计划一-Run")
