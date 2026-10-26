"""更新用例：版本递增、乐观锁 40003、状态机 40004、审计 diff。"""
import re

from apps.audit.models import AuditLog
from apps.testcases.models import TestCaseVersion
from apps.testcases.tests.base import NanoTestCase

ISO_MICROSECOND = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}")


class UpdateTestCaseTests(NanoTestCase):
    def test_content_change_creates_new_version_and_bumps_current_version(self):
        created = self.create_case(title="原始标题")
        response = self.patch_case(created["id"], {
            "updated_at": created["updated_at"],
            "title": "新标题",
            "steps": [{"action": "点击登录", "expected": "跳转首页"}],
            "change_summary": "修改标题与步骤",
        })
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]

        self.assertEqual(data["current_version"], 2)
        self.assertEqual(data["title"], "新标题")
        self.assertEqual(data["change_summary"], "修改标题与步骤")
        self.assertNotEqual(data["updated_at"], created["updated_at"])

        versions = TestCaseVersion.objects.filter(test_case_id=created["id"]).order_by("version")
        self.assertEqual([version.version for version in versions], [1, 2])
        self.assertEqual(versions[1].title, "新标题")
        self.assertEqual(versions[1].change_summary, "修改标题与步骤")
        self.assertEqual(versions[1].created_by_id, self.user.id)
        self.assertEqual(versions[1].steps, [{"order": 1, "action": "点击登录", "expected": "跳转首页"}])
        # 旧版本快照不受影响（坑 4）
        self.assertEqual(versions[0].title, "原始标题")

    def test_expected_result_and_description_changes_also_versioned(self):
        created = self.create_case()
        response = self.patch_case(created["id"], {
            "updated_at": created["updated_at"],
            "expected_result": "支付成功",
            "description": "补充描述",
        })
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual(data["current_version"], 2)
        self.assertEqual(data["expected_result"], "支付成功")
        self.assertEqual(data["description"], "补充描述")

    def test_non_content_change_does_not_create_version(self):
        created = self.create_case()
        response = self.patch_case(created["id"], {
            "updated_at": created["updated_at"],
            "priority": "P0",
            "case_type": "smoke",
        })
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual(data["current_version"], 1)
        self.assertEqual(data["priority"], "P0")
        self.assertEqual(TestCaseVersion.objects.filter(test_case_id=created["id"]).count(), 1)

    def test_missing_updated_at_rejected_with_40003(self):
        created = self.create_case()
        response = self.patch_case(created["id"], {"title": "无锁更新"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], 40003)

    def test_stale_updated_at_conflict_40003(self):
        created = self.create_case()
        stale = created["updated_at"]

        first = self.patch_case(created["id"], {"updated_at": stale, "title": "第一次修改"})
        self.assertEqual(first.status_code, 200, first.content)
        fresh = first.json()["data"]["updated_at"]
        self.assertNotEqual(fresh, stale)

        # 用旧值回传 → 冲突
        conflict = self.patch_case(created["id"], {"updated_at": stale, "title": "第二次修改"})
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["code"], 40003)

        # 用新值回传 → 成功（乐观锁版本字段 ISO 微秒可原样回传）
        ok = self.patch_case(created["id"], {"updated_at": fresh, "title": "第二次修改"})
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertEqual(ok.json()["data"]["title"], "第二次修改")

    def test_updated_at_output_is_iso_with_microseconds(self):
        created = self.create_case()
        self.assertTrue(ISO_MICROSECOND.match(created["updated_at"]), created["updated_at"])
        self.assertTrue(ISO_MICROSECOND.match(created["created_at"]), created["created_at"])

    def test_invalid_status_transition_40004(self):
        created = self.create_case(status="draft")
        response = self.patch_case(created["id"], {
            "updated_at": created["updated_at"],
            "status": "deprecated",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], 40004)

    def test_valid_status_transition_chain(self):
        created = self.create_case(status="draft")
        active = self.patch_case(created["id"], {"updated_at": created["updated_at"], "status": "active"})
        self.assertEqual(active.status_code, 200, active.content)
        self.assertEqual(active.json()["data"]["status"], "active")

        deprecated = self.patch_case(created["id"], {
            "updated_at": active.json()["data"]["updated_at"],
            "status": "deprecated",
        })
        self.assertEqual(deprecated.status_code, 200, deprecated.content)
        self.assertEqual(deprecated.json()["data"]["status"], "deprecated")
        # 状态流转不产生新版本
        self.assertEqual(deprecated.json()["data"]["current_version"], 1)

    def test_update_maintains_tags_owner_module_and_automation(self):
        created = self.create_case(tag_ids=[self.tag_smoke.id], module_id=self.module.id)
        response = self.patch_case(created["id"], {
            "updated_at": created["updated_at"],
            "tag_ids": [self.tag_fast.id],
            "owner_id": self.owner.id,
            "module_id": self.child_module.id,
            "automation_status": "automated",
            "automation_framework": "playwright",
            "automation_identifier": "spec/login.spec.ts",
        })
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual([tag["id"] for tag in data["tags"]], [self.tag_fast.id])
        self.assertEqual(data["owner"]["id"], self.owner.id)
        self.assertEqual(data["module_id"], self.child_module.id)
        self.assertEqual(data["module_name"], "Password")
        self.assertEqual(data["automation_status"], "automated")
        self.assertEqual(data["automation_framework"], "playwright")

    def test_update_records_audit_diff(self):
        created = self.create_case(title="旧标题")
        self.patch_case(created["id"], {"updated_at": created["updated_at"], "title": "新标题"})
        audit = (
            AuditLog.objects.filter(object_type="testcase", object_id=created["id"], action="update")
            .order_by("-id")
            .first()
        )
        self.assertIsNotNone(audit)
        self.assertEqual(audit.old_data.get("title"), "旧标题")
        self.assertEqual(audit.new_data.get("title"), "新标题")
        self.assertEqual(audit.object_ref, created["case_key"])
