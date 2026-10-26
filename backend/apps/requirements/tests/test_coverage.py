"""需求↔用例关联与覆盖率口径测试（§37）。"""
from apps.requirements.models import RequirementTestCase
from apps.requirements.tests.base import NanoAPITestCase


class RequirementLinkTests(NanoAPITestCase):
    def link_url(self, req):
        return f"/api/v1/requirements/{req.pk}/testcases/"

    def test_link_and_unlink_testcases(self):
        req = self.make_requirement()
        case1, case2 = self.make_testcase(), self.make_testcase()
        self.login(self.qa)

        data = self.assertCode(
            self.client.post(self.link_url(req), {"test_case_ids": [case1.pk, case2.pk]}, format="json"), 0
        )
        self.assertEqual(sorted(data["linked_test_case_ids"]), sorted([case1.pk, case2.pk]))
        self.assertEqual(RequirementTestCase.objects.filter(requirement=req).count(), 2)

        # 重复关联幂等
        data = self.assertCode(
            self.client.post(self.link_url(req), {"test_case_ids": [case1.pk]}, format="json"), 0
        )
        self.assertEqual(data["linked_test_case_ids"], [])

        # body 解绑
        data = self.assertCode(
            self.client.delete(self.link_url(req), {"test_case_id": case1.pk}, format="json"), 0
        )
        self.assertEqual(data["unlinked_test_case_id"], case1.pk)

        # 路径解绑
        data = self.assertCode(self.client.delete(f"{self.link_url(req)}{case2.pk}/"), 0)
        self.assertEqual(data["unlinked_test_case_id"], case2.pk)
        self.assertEqual(RequirementTestCase.objects.filter(requirement=req).count(), 0)

    def test_link_foreign_project_case_rejected(self):
        from apps.projects.models import Project

        other_project = Project.objects.create(
            organization=self.org, name="其他项目", key="OTHR", owner=self.owner
        )
        foreign = self.make_testcase(project=other_project)
        req = self.make_requirement()
        self.login(self.qa)
        r = self.client.post(self.link_url(req), {"test_case_ids": [foreign.pk]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], 40006)

    def test_link_requires_update_permission(self):
        req = self.make_requirement()
        case = self.make_testcase()
        self.login(self.viewer)  # viewer 无 requirement.update
        r = self.client.post(self.link_url(req), {"test_case_ids": [case.pk]}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], 40001)


class RequirementCoverageTests(NanoAPITestCase):
    def coverage_url(self, req):
        return f"/api/v1/requirements/{req.pk}/coverage/"

    def link(self, req, case_ids):
        self.assertCode(
            self.client.post(
                f"/api/v1/requirements/{req.pk}/testcases/", {"test_case_ids": case_ids}, format="json"
            ),
            0,
        )

    def test_coverage_counts_latest_result_per_case(self):
        req = self.make_requirement()
        case1, case2, case3 = self.make_testcase(), self.make_testcase(), self.make_testcase()
        self.login(self.qa)
        self.link(req, [case1.pk, case2.pk, case3.pk])

        run1, run2 = self.make_run("run1"), self.make_run("run2")
        self.make_result(run1, case1, "failed")   # 旧结果，应被覆盖
        self.make_result(run2, case1, "passed")   # 最新结果
        self.make_result(run1, case2, "failed")

        data = self.assertCode(self.client.get(self.coverage_url(req)), 0)
        self.assertEqual(data["linked_cases"], 3)
        self.assertEqual(data["executed"], 2)
        self.assertEqual(data["passed"], 1)
        self.assertEqual(data["failed"], 1)
        self.assertEqual(data["blocked"], 0)
        self.assertEqual(data["not_run"], 1)
        self.assertEqual(data["coverage"], 1.0)  # 缺省 expected = linked
        self.assertEqual(data["risk_level"], "medium")  # 有 failed

    def test_coverage_with_expected_cases_param(self):
        req = self.make_requirement()
        case1, case2 = self.make_testcase(), self.make_testcase()
        self.login(self.qa)
        self.link(req, [case1.pk, case2.pk])
        run = self.make_run()
        self.make_result(run, case1, "passed")
        self.make_result(run, case2, "passed")

        data = self.assertCode(self.client.get(f"{self.coverage_url(req)}?expected_cases=4"), 0)
        self.assertEqual(data["expected_cases"], 4)
        self.assertEqual(data["coverage"], 0.5)
        self.assertEqual(data["risk_level"], "low")  # 全 passed

    def test_coverage_without_links_high_risk(self):
        req = self.make_requirement()
        self.login(self.qa)
        data = self.assertCode(self.client.get(self.coverage_url(req)), 0)
        self.assertEqual(data["linked_cases"], 0)
        self.assertEqual(data["executed"], 0)
        self.assertEqual(data["coverage"], 0.0)
        self.assertEqual(data["risk_level"], "high")

    def test_coverage_excludes_soft_deleted_case(self):
        req = self.make_requirement()
        case = self.make_testcase()
        self.login(self.qa)
        self.link(req, [case.pk])
        run = self.make_run()
        self.make_result(run, case, "passed")
        case.soft_delete()

        data = self.assertCode(self.client.get(self.coverage_url(req)), 0)
        self.assertEqual(data["linked_cases"], 0)
        self.assertEqual(data["risk_level"], "high")

    def test_coverage_invalid_expected_cases(self):
        req = self.make_requirement()
        self.login(self.qa)
        r = self.client.get(f"{self.coverage_url(req)}?expected_cases=abc")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], 40006)
