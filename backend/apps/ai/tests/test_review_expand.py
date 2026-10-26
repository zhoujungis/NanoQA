"""AI 用例评审 / 边界扩展：Mock 规则扣分 + AITask 落库。"""
from rest_framework.test import APITestCase

from apps.ai.models import AITask
from apps.ai.tests import helpers


class ReviewExpandTests(APITestCase):
    def setUp(self):
        self.user = helpers.make_user()
        self.project = helpers.make_project(self.user)
        self.client.force_authenticate(self.user)

    def test_review_scores_by_rules(self):
        # 1 条步骤 + 标题过短 → 扣分并给出 issues
        case = helpers.make_case(
            self.project, self.user, title="简短标题",
            steps=[{"order": 1, "action": "打开页面", "expected": "加载成功"}],
            expected_result="",
        )
        response = self.client.post(f"/api/v1/ai/testcases/{case.id}/review/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertLess(data["score"], 100)
        self.assertGreaterEqual(data["score"], 0)
        self.assertTrue(data["issues"])
        self.assertTrue(all(issue["severity"] in {"high", "medium", "low"} for issue in data["issues"]))
        self.assertTrue(data["suggestions"])

        task = AITask.objects.get(pk=data["task_id"])
        self.assertEqual(task.task_type, "review_testcase")
        self.assertEqual(task.status, AITask.STATUS_SUCCEEDED)
        self.assertEqual(task.output_data["score"], data["score"])

    def test_review_complete_case_scores_full(self):
        case = helpers.make_case(
            self.project, self.user, title="用户登录正确账号密码登录成功验证",
            steps=[
                {"order": 1, "action": "打开登录页", "expected": "展示表单"},
                {"order": 2, "action": "输入正确账号密码", "expected": "校验通过"},
                {"order": 3, "action": "点击登录", "expected": "跳转首页"},
            ],
        )
        response = self.client.post(f"/api/v1/ai/testcases/{case.id}/review/")
        data = response.json()["data"]
        self.assertEqual(data["score"], 100)
        self.assertEqual(data["issues"], [])

    def test_expand_returns_edge_case_preview(self):
        case = helpers.make_case(self.project, self.user, title="用户登录验证")
        response = self.client.post(
            f"/api/v1/ai/testcases/{case.id}/expand/", {"count": 3}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data["cases"]), 3)

        task = AITask.objects.get(pk=data["task_id"])
        self.assertEqual(task.task_type, "expand_edge_cases")
        self.assertEqual(task.input_data["test_case_id"], case.id)
        self.assertFalse(task.output_data.get("accepted"))

    def test_review_unknown_case_returns_404(self):
        response = self.client.post("/api/v1/ai/testcases/99999/review/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], 40005)
