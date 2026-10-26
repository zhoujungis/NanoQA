"""缺陷关联（用例/需求/执行结果）与状态时间线测试。"""
from apps.defects.models import RequirementDefect, TestCaseDefect, TestResultDefect
from apps.defects.tests.base import NanoAPITestCase


class DefectLinkTests(NanoAPITestCase):
    def detail_url(self, defect):
        return f"/api/v1/defects/{defect.pk}/"

    def create_defect_via_api(self, title="接口缺陷"):
        self.login(self.qa)
        return self.assertCode(self.client.post(f"/api/v1/projects/{self.project.pk}/defects/", {"title": title}, format="json"), 0)

    # ---------------------------------------------------------------- 用例关联
    def test_link_and_unlink_testcases(self):
        data = self.create_defect_via_api()
        defect_id = data["id"]
        case1, case2 = self.make_testcase(), self.make_testcase()

        linked = self.assertCode(
            self.client.post(
                f"/api/v1/defects/{defect_id}/testcases/",
                {"test_case_ids": [case1.pk, case2.pk]},
                format="json",
            ),
            0,
        )
        self.assertEqual(sorted(linked["linked_test_case_ids"]), sorted([case1.pk, case2.pk]))
        self.assertEqual(TestCaseDefect.objects.filter(defect_id=defect_id).count(), 2)

        # 重复关联幂等
        linked = self.client.post(
            f"/api/v1/defects/{defect_id}/testcases/", {"test_case_ids": [case1.pk]}, format="json"
        )
        self.assertEqual(self.assertCode(linked, 0)["linked_test_case_ids"], [])

        r = self.client.delete(f"/api/v1/defects/{defect_id}/testcases/{case1.pk}/")
        self.assertEqual(self.assertCode(r, 0)["unlinked_test_case_id"], case1.pk)
        r = self.client.delete(f"/api/v1/defects/{defect_id}/testcases/{case2.pk}/")
        self.assertCode(r, 0)
        self.assertEqual(TestCaseDefect.objects.filter(defect_id=defect_id).count(), 0)

    # ---------------------------------------------------------------- 需求关联
    def test_link_and_unlink_requirements(self):
        data = self.create_defect_via_api()
        defect_id = data["id"]
        requirement = self.make_requirement()

        linked = self.assertCode(
            self.client.post(
                f"/api/v1/defects/{defect_id}/requirements/", {"requirement_ids": [requirement.pk]}, format="json"
            ),
            0,
        )
        self.assertEqual(linked["linked_requirement_ids"], [requirement.pk])
        self.assertTrue(RequirementDefect.objects.filter(defect_id=defect_id, requirement=requirement).exists())

        r = self.client.delete(f"/api/v1/defects/{defect_id}/requirements/{requirement.pk}/")
        self.assertEqual(self.assertCode(r, 0)["unlinked_requirement_id"], requirement.pk)
        self.assertFalse(RequirementDefect.objects.filter(defect_id=defect_id).exists())

    def test_link_foreign_project_requirement_rejected(self):
        from apps.projects.models import Project

        other_project = Project.objects.create(
            organization=self.org, name="其他项目", key="OTHR", owner=self.owner
        )
        foreign = self.make_requirement(project=other_project)
        data = self.create_defect_via_api()
        r = self.client.post(
            f"/api/v1/defects/{data['id']}/requirements/", {"requirement_ids": [foreign.pk]}, format="json"
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], 40006)

    def test_link_requires_update_permission(self):
        defect = self.make_defect()
        case = self.make_testcase()
        self.login(self.viewer)  # viewer 无 defect.update
        r = self.client.post(f"/api/v1/defects/{defect.pk}/testcases/", {"test_case_ids": [case.pk]}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], 40001)

    # ---------------------------------------------------------------- 详情与时间线
    def test_detail_includes_links_results_and_timeline(self):
        data = self.create_defect_via_api(title="详情缺陷")
        defect_id = data["id"]
        case = self.make_testcase()
        requirement = self.make_requirement()
        self.assertCode(
            self.client.post(
                f"/api/v1/defects/{defect_id}/testcases/", {"test_case_ids": [case.pk]}, format="json"
            ),
            0,
        )
        self.assertCode(
            self.client.post(
                f"/api/v1/defects/{defect_id}/requirements/", {"requirement_ids": [requirement.pk]}, format="json"
            ),
            0,
        )
        # 执行结果关联（FAIL 建缺陷场景）
        run = self.make_run()
        result = self.make_result(run, case, "failed")
        TestResultDefect.objects.create(test_result=result, defect_id=defect_id)

        detail = self.assertCode(self.client.get(f"/api/v1/defects/{defect_id}/"), 0)
        self.assertEqual([c["id"] for c in detail["test_cases"]], [case.pk])
        self.assertEqual([q["id"] for q in detail["requirements"]], [requirement.pk])
        self.assertEqual([r["id"] for r in detail["test_results"]], [result.pk])
        self.assertEqual(detail["test_results"][0]["status"], "failed")

        # 状态时间线：create → link → link → transition
        timeline = detail["timeline"]
        self.assertGreaterEqual(len(timeline), 2)
        self.assertEqual(timeline[0]["action"], "create")
        self.assertEqual(timeline[0]["to_status"], "Open")

        detail = self.assertCode(
            self.client.patch(
                f"/api/v1/defects/{defect_id}/",
                {"status": "In Progress", "updated_at": detail["updated_at"]},
                format="json",
            ),
            0,
        )
        timeline = self.assertCode(self.client.get(f"/api/v1/defects/{defect_id}/"), 0)["timeline"]
        entry = [e for e in timeline if e["action"] == "transition"][0]
        self.assertEqual(entry["from_status"], "Open")
        self.assertEqual(entry["to_status"], "In Progress")
        self.assertEqual(entry["user"]["id"], self.qa.pk)
