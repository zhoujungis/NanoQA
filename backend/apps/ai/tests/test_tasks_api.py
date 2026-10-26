"""AI 任务列表 / 详情端点：分页 + task_type 过滤。"""
from rest_framework.test import APITestCase

from apps.ai.models import AITask
from apps.ai.tests import helpers


class AITaskListTests(APITestCase):
    def setUp(self):
        self.user = helpers.make_user()
        self.project = helpers.make_project(self.user)
        self.client.force_authenticate(self.user)

    def _make_task(self, task_type: str) -> AITask:
        return AITask.objects.create(
            organization=self.project.organization, project=self.project, user=self.user,
            task_type=task_type, input_data={"k": 1}, output_data={"cases": helpers.fake_cases(1)},
            status=AITask.STATUS_SUCCEEDED, model="mock",
        )

    def test_list_filter_by_task_type(self):
        generate_task = self._make_task("generate_testcases")
        self._make_task("review_testcase")

        response = self.client.get(
            f"/api/v1/ai/tasks/?project_id={self.project.id}&task_type=generate_testcases"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["id"], generate_task.id)
        self.assertEqual(data["items"][0]["task_type"], "generate_testcases")
        self.assertEqual(data["page"], 1)

    def test_list_all_for_project(self):
        self._make_task("generate_testcases")
        self._make_task("detect_duplicate_cases")
        response = self.client.get(f"/api/v1/ai/tasks/?project_id={self.project.id}")
        self.assertEqual(response.json()["data"]["total"], 2)

    def test_detail(self):
        task = self._make_task("generate_testcases")
        response = self.client.get(f"/api/v1/ai/tasks/{task.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["id"], task.id)
        self.assertEqual(data["status"], AITask.STATUS_SUCCEEDED)
        self.assertEqual(data["user"]["id"], self.user.id)
