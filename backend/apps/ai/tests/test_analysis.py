"""需求分析 / 缺陷分析端点：结构化输出 + AITask 落库。"""
from rest_framework.test import APITestCase

from apps.ai.models import AITask
from apps.ai.tests import helpers
from apps.defects.models import Defect, TestCaseDefect
from apps.projects.services.keys import next_key
from apps.requirements.models import Requirement


class AnalyzeTests(APITestCase):
    def setUp(self):
        self.user = helpers.make_user()
        self.project = helpers.make_project(self.user)
        self.client.force_authenticate(self.user)

    def test_requirement_analyze(self):
        requirement = Requirement.objects.create(
            organization=self.project.organization, project=self.project,
            key=next_key(self.project, "REQ"), title="用户登录", description="支持账号密码登录",
            creator=self.user,
        )
        response = self.client.post(f"/api/v1/ai/requirements/{requirement.id}/analyze/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["summary"])
        self.assertTrue(data["suggested_cases"])
        self.assertTrue(data["risks"])

        task = AITask.objects.get(pk=data["task_id"])
        self.assertEqual(task.task_type, "analyze_requirement")
        self.assertEqual(task.status, AITask.STATUS_SUCCEEDED)

    def test_defect_analyze_returns_related_case_ids(self):
        case = helpers.make_case(self.project, self.user, title="登录失败用例")
        defect = Defect.objects.create(
            organization=self.project.organization, project=self.project,
            key=next_key(self.project, "BUG"), title="登录 500 错误", description="登录接口报错",
            reporter=self.user,
        )
        TestCaseDefect.objects.create(test_case=case, defect=defect)

        response = self.client.post(f"/api/v1/ai/defects/{defect.id}/analyze/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["possible_causes"])
        self.assertTrue(data["suggestions"])
        self.assertEqual(data["related_case_ids"], [case.id])

        task = AITask.objects.get(pk=data["task_id"])
        self.assertEqual(task.task_type, "analyze_defect")

    def test_analyze_unknown_defect_returns_404(self):
        response = self.client.post("/api/v1/ai/defects/99999/analyze/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], 40005)
