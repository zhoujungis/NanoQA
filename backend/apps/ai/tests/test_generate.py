"""AI 用例生成：Mock 通过路 + Schema 校验失败路（status=failed + error）。"""
from unittest.mock import patch

from rest_framework.test import APITestCase

from apps.ai.models import AITask
from apps.ai.services.schema import SchemaValidationError, validate_generated_cases
from apps.ai.tests import helpers


class BrokenProvider:
    """输出非法结构，触发 JSON Schema 二次校验失败。"""

    name = "broken"

    def complete(self, prompt, schema=None):
        return {"cases": [{"title": "", "priority": "P9", "type": "unknown", "steps": []}]}


class GenerateTestcasesTests(APITestCase):
    def setUp(self):
        self.user = helpers.make_user()
        self.project = helpers.make_project(self.user)
        self.client.force_authenticate(self.user)

    def test_generate_with_mock_provider(self):
        response = self.client.post(
            "/api/v1/ai/testcases/generate/",
            {"project_id": self.project.id, "title_hint": "用户登录", "count": 3,
             "include_edge_cases": True, "include_security": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["status"], AITask.STATUS_SUCCEEDED)
        self.assertEqual(len(data["cases"]), 3)
        for case in data["cases"]:
            self.assertTrue(case["title"])
            self.assertIn(case["priority"], {"P0", "P1", "P2", "P3"})
            self.assertTrue(case["steps"])
            self.assertTrue(all(step["action"] and step["expected"] for step in case["steps"]))

        task = AITask.objects.get(pk=data["task_id"])
        self.assertEqual(task.task_type, "generate_testcases")
        self.assertEqual(task.status, AITask.STATUS_SUCCEEDED)
        self.assertEqual(task.model, "mock")
        self.assertGreater(task.tokens, 0)
        self.assertGreaterEqual(task.duration, 0)
        self.assertEqual(task.input_data["count"], 3)
        self.assertEqual(len(task.output_data["cases"]), 3)
        self.assertFalse(task.output_data.get("accepted"))

    def test_generate_from_requirement(self):
        from apps.requirements.models import Requirement
        from apps.projects.services.keys import next_key

        requirement = Requirement.objects.create(
            organization=self.project.organization, project=self.project,
            key=next_key(self.project, "REQ"), title="用户登录", description="支持账号密码登录",
            creator=self.user,
        )
        response = self.client.post(
            "/api/v1/ai/testcases/generate/",
            {"requirement_id": requirement.id, "count": 2},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data["cases"]), 2)
        task = AITask.objects.get(pk=data["task_id"])
        self.assertEqual(task.project_id, self.project.id)
        self.assertEqual(task.input_data["requirement_id"], requirement.id)

    def test_schema_validation_failure_marks_task_failed(self):
        with patch("apps.ai.services.llm.get_provider", return_value=BrokenProvider()):
            response = self.client.post(
                "/api/v1/ai/testcases/generate/",
                {"project_id": self.project.id, "title_hint": "登录", "count": 1},
                format="json",
            )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["code"], 40006)
        task = AITask.objects.get(pk=body["data"]["task_id"])
        self.assertEqual(task.status, AITask.STATUS_FAILED)
        self.assertTrue(task.error)
        self.assertEqual(task.project_id, self.project.id)

    def test_count_out_of_range_rejected(self):
        response = self.client.post(
            "/api/v1/ai/testcases/generate/",
            {"project_id": self.project.id, "count": 60},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], 40006)
        self.assertEqual(AITask.objects.count(), 0)

    def test_schema_validator_unit(self):
        good = {"cases": [{"title": "用例", "priority": "P1", "type": "functional",
                          "steps": [{"action": "a", "expected": "e"}]}]}
        self.assertEqual(len(validate_generated_cases(good)), 1)

        with self.assertRaises(SchemaValidationError):
            validate_generated_cases({"cases": [{"title": "用例", "priority": "P1",
                                                 "type": "functional", "steps": [{"action": "", "expected": "e"}]}]})
        with self.assertRaises(SchemaValidationError):
            validate_generated_cases({"cases": []})
