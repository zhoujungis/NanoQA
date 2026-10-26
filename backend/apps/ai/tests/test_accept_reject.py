"""AI 任务人工审核：accept 转正式 Draft 用例（坑 3），reject 只标记不入库。"""
from rest_framework.test import APITestCase

from apps.ai.models import AITask
from apps.ai.tests import helpers
from apps.audit.models import AuditLog
from apps.testcases.models import TestCase, TestCaseVersion


class AcceptRejectTests(APITestCase):
    def setUp(self):
        self.user = helpers.make_user()
        self.project = helpers.make_project(self.user)
        self.client.force_authenticate(self.user)
        # 审计落库需要 User-Agent（audit.user_agent 非空列）
        self.client.credentials(HTTP_USER_AGENT="nanoqa-tests")

    def _make_task(self, cases=None) -> AITask:
        return AITask.objects.create(
            organization=self.project.organization, project=self.project, user=self.user,
            task_type="generate_testcases", input_data={"count": 3},
            output_data={"cases": cases if cases is not None else helpers.fake_cases(3)},
            status=AITask.STATUS_SUCCEEDED, model="mock",
        )

    def test_accept_creates_draft_cases_with_version(self):
        task = self._make_task()
        response = self.client.post(f"/api/v1/ai/tasks/{task.id}/accept/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data["cases"]), 3)

        self.assertEqual(TestCase.objects.count(), 3)
        self.assertEqual(TestCase.objects.filter(status=TestCase.STATUS_DRAFT).count(), 3)
        for case in TestCase.objects.all():
            self.assertTrue(case.case_key.startswith(f"{self.project.key}-TC-"))
            self.assertEqual(case.organization_id, self.project.organization_id)
            self.assertEqual(case.creator_id, self.user.id)
            self.assertEqual(case.current_version, 1)

        self.assertEqual(TestCaseVersion.objects.count(), 3)
        version = TestCaseVersion.objects.get(test_case__title="AI 生成用例1")
        self.assertEqual(version.version, 1)
        self.assertEqual(version.steps[0]["order"], 1)
        self.assertEqual(version.steps[0]["action"], "执行步骤1-1")

        task.refresh_from_db()
        self.assertTrue(task.output_data["accepted"])
        self.assertEqual(len(task.output_data["accepted_case_ids"]), 3)

        case_audits = AuditLog.objects.filter(action=AuditLog.ACTION_CREATE, object_type="testcase")
        self.assertEqual(case_audits.count(), 3)

    def test_accept_twice_conflicts(self):
        task = self._make_task()
        self.client.post(f"/api/v1/ai/tasks/{task.id}/accept/")
        response = self.client.post(f"/api/v1/ai/tasks/{task.id}/accept/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], 40007)
        self.assertEqual(TestCase.objects.count(), 3)

    def test_reject_marks_rejected_without_persisting(self):
        task = self._make_task()
        response = self.client.post(f"/api/v1/ai/tasks/{task.id}/reject/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["rejected"])

        task.refresh_from_db()
        self.assertTrue(task.output_data["rejected"])
        self.assertEqual(TestCase.objects.count(), 0)
        self.assertEqual(AuditLog.objects.filter(action=AuditLog.ACTION_UPDATE, object_type="aitask").count(), 1)

    def test_reject_after_accept_conflicts(self):
        task = self._make_task()
        self.client.post(f"/api/v1/ai/tasks/{task.id}/accept/")
        response = self.client.post(f"/api/v1/ai/tasks/{task.id}/reject/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], 40007)
