"""重复用例检测：difflib 相似度 ≥0.6 输出、降序、最多 50 对。"""
from rest_framework.test import APITestCase

from apps.ai.models import AITask
from apps.ai.tests import helpers

SIMILAR_STEPS = [
    {"order": 1, "action": "打开登录页面", "expected": "显示登录表单"},
    {"order": 2, "action": "输入正确账号密码", "expected": "登录成功跳转首页"},
]


class DetectDuplicatesTests(APITestCase):
    def setUp(self):
        self.user = helpers.make_user()
        self.project = helpers.make_project(self.user)
        self.client.force_authenticate(self.user)

    def _detect(self):
        response = self.client.post(
            "/api/v1/ai/testcases/detect-duplicates/", {"project_id": self.project.id}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def test_detects_similar_pairs_and_sorts_desc(self):
        case_a = helpers.make_case(self.project, self.user, title="用户登录-输入正确账号密码后登录成功验证", steps=SIMILAR_STEPS)
        case_b = helpers.make_case(self.project, self.user, title="用户登录-输入正确账号密码后登录成功校验", steps=SIMILAR_STEPS)
        helpers.make_case(
            self.project, self.user, title="订单退款审批链路覆盖",
            steps=[
                {"order": 1, "action": "提交退款申请", "expected": "生成退款单"},
                {"order": 2, "action": "财务审核", "expected": "审核通过"},
                {"order": 3, "action": "资金退回", "expected": "退款到账"},
            ],
        )

        data = self._detect()
        pairs = data["pairs"]
        self.assertEqual(len(pairs), 1)
        self.assertEqual({pairs[0]["case_a"], pairs[0]["case_b"]}, {case_a.id, case_b.id})
        self.assertGreaterEqual(pairs[0]["similarity"], 0.6)

        task = AITask.objects.get(pk=data["task_id"])
        self.assertEqual(task.task_type, "detect_duplicate_cases")
        self.assertEqual(task.output_data["pairs"], pairs)

    def test_pairs_capped_at_50(self):
        for index in range(11):
            helpers.make_case(self.project, self.user, title=f"重复用例{index}", steps=SIMILAR_STEPS)

        pairs = self._detect()["pairs"]
        self.assertEqual(len(pairs), 50)
        similarities = [pair["similarity"] for pair in pairs]
        self.assertEqual(similarities, sorted(similarities, reverse=True))

    def test_no_pairs_for_distinct_cases(self):
        helpers.make_case(self.project, self.user, title="用户登录功能验证", steps=SIMILAR_STEPS)
        helpers.make_case(
            self.project, self.user, title="库存盘点差异处理",
            steps=[{"order": 1, "action": "导入盘点单", "expected": "生成差异表"}],
        )
        self.assertEqual(self._detect()["pairs"], [])
