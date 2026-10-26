"""创建用例：用例 + 版本 + 审计同事务、steps 校验、编号唯一递增。"""
import threading
from unittest import mock

from django.db import connection
from django.test import TransactionTestCase

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.organizations.models import Organization
from apps.projects.models import Module, Project, Tag
from apps.testcases.models import TestCase, TestCaseVersion
from apps.testcases.services.cases import create_case as create_case_service
from apps.testcases.tests.base import NanoTestCase


class CreateTestCaseTests(NanoTestCase):
    def test_create_case_version_and_audit_in_one_transaction(self):
        response = self.client.post(
            self.list_url,
            self.payload(
                title="下单支付",
                priority="P0",
                case_type="regression",
                precondition="用户已登录",
                expected_result="支付成功",
                description="覆盖主流程",
                module_id=self.module.id,
                tag_ids=[self.tag_smoke.id, self.tag_fast.id],
                owner_id=self.owner.id,
                status="active",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]

        self.assertEqual(data["case_key"], "SHOP-TC-000001")
        self.assertEqual(data["current_version"], 1)
        self.assertEqual(data["priority"], "P0")
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["owner"]["id"], self.owner.id)
        self.assertEqual(data["creator"]["id"], self.user.id)
        self.assertEqual(sorted(tag["id"] for tag in data["tags"]), sorted([self.tag_smoke.id, self.tag_fast.id]))
        self.assertEqual(data["steps"], [{"order": 1, "action": "打开登录页", "expected": "登录页正常展示"}])
        self.assertEqual(data["expected_result"], "支付成功")
        self.assertEqual(data["module_path"][-1]["name"], "Login")

        case = TestCase.objects.get(pk=data["id"])
        version = TestCaseVersion.objects.get(test_case=case, version=1)
        self.assertEqual(version.change_summary, "初始版本")
        self.assertEqual(version.title, "下单支付")
        self.assertEqual(version.steps, case.versions.get(version=1).steps)
        self.assertEqual(version.expected_result, "支付成功")
        self.assertEqual(case.current_version, 1)
        self.assertEqual(case.organization_id, self.org.id)

        audit = AuditLog.objects.get(object_type="testcase", object_id=case.pk)
        self.assertEqual(audit.action, "create")
        self.assertEqual(audit.object_ref, case.case_key)
        self.assertEqual(audit.user_id, self.user.id)
        self.assertEqual(audit.project_id, self.project.id)

    def test_create_rolls_back_everything_when_audit_fails(self):
        with mock.patch(
            "apps.testcases.services.cases.AuditService.record",
            side_effect=RuntimeError("audit down"),
        ):
            response = self.client.post(self.list_url, self.payload(), format="json")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["code"], 50000)
        self.assertEqual(TestCase.objects.filter(project=self.project).count(), 0)
        self.assertEqual(TestCaseVersion.objects.count(), 0)
        self.assertEqual(AuditLog.objects.filter(object_type="testcase").count(), 0)

    def test_steps_must_be_non_empty_list(self):
        for bad_steps in ([], {}, "abc", None):
            response = self.client.post(self.list_url, self.payload(steps=bad_steps), format="json")
            self.assertEqual(response.status_code, 400, bad_steps)
            self.assertEqual(response.json()["code"], 40006)

    def test_steps_items_require_action_and_expected(self):
        cases = [
            [{"action": "点击", "expected": ""}],
            [{"action": "点击"}],
            [{"expected": "成功"}],
            [{"action": "  ", "expected": "成功"}],
            [["不是对象"]],
        ]
        for bad_steps in cases:
            response = self.client.post(self.list_url, self.payload(steps=bad_steps), format="json")
            self.assertEqual(response.status_code, 400, bad_steps)
            self.assertEqual(response.json()["code"], 40006)

    def test_steps_order_is_renumbered_1_to_n(self):
        data = self.create_case(steps=[
            {"order": 5, "action": "第一步", "expected": "ok"},
            {"order": 2, "action": "第二步", "expected": "ok"},
            {"action": "第三步", "expected": "ok"},
        ])
        self.assertEqual([step["order"] for step in data["steps"]], [1, 2, 3])
        self.assertEqual([step["action"] for step in data["steps"]], ["第一步", "第二步", "第三步"])

    def test_missing_required_fields_rejected(self):
        for key in ("title", "priority", "steps"):
            payload = self.payload()
            payload.pop(key)
            response = self.client.post(self.list_url, payload, format="json")
            self.assertEqual(response.status_code, 400, key)
            self.assertEqual(response.json()["code"], 40006)

    def test_create_status_only_draft_or_active(self):
        response = self.client.post(self.list_url, self.payload(status="archived"), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], 40006)

    def test_foreign_module_and_tag_rejected(self):
        other_project = Project.objects.create(
            organization=self.org, name="Other", key="OTHR", owner=self.user
        )
        other_module = Module.objects.create(project=other_project, name="OtherModule")
        other_tag = Tag.objects.create(project=other_project, name="other-tag")

        response = self.client.post(self.list_url, self.payload(module_id=other_module.id), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], 40006)

        response = self.client.post(self.list_url, self.payload(tag_ids=[other_tag.id]), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], 40006)
        self.assertEqual(TestCase.objects.filter(project=self.project).count(), 0)

    def test_case_keys_are_unique_and_monotonic(self):
        keys = [self.create_case(title=f"用例 {index}")["case_key"] for index in range(3)]
        self.assertEqual(keys, ["SHOP-TC-000001", "SHOP-TC-000002", "SHOP-TC-000003"])
        self.assertEqual(len(set(keys)), 3)


class CaseKeyConcurrencyTests(TransactionTestCase):
    """并发建用例：编号 select_for_update 取号，单调递增、永不复用（§49）。"""

    # TransactionTestCase 结束时 flush 会截断数据迁移种子（Role/Permission），
    # 必须回滚序列化快照，否则污染后续用例（--keepdb 下尤其严重）。
    serialized_rollback = True

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pass12345"
        )
        self.org = Organization.objects.create(name="Nano Org", slug="nano-org", owner=self.user)
        self.project = Project.objects.create(
            organization=self.org, name="Shop", key="SHOP", owner=self.user
        )

    def test_case_keys_unique_under_concurrency(self):
        thread_count, per_thread = 8, 5
        errors = []

        def worker(seed):
            try:
                for index in range(per_thread):
                    create_case_service(
                        self.project,
                        {
                            "title": f"并发用例-{seed}-{index}",
                            "priority": "P1",
                            "steps": [{"order": 1, "action": "操作", "expected": "预期"}],
                        },
                        user=self.user,
                    )
            except Exception as exc:  # noqa: BLE001 - 收集后统一断言
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(seed,)) for seed in range(thread_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        keys = list(
            TestCase.objects.filter(project=self.project).order_by("id").values_list("case_key", flat=True)
        )
        self.assertEqual(len(keys), thread_count * per_thread)
        self.assertEqual(len(set(keys)), len(keys))
        numbers = sorted(int(key.rsplit("-", 1)[1]) for key in keys)
        self.assertEqual(numbers, list(range(1, thread_count * per_thread + 1)))
