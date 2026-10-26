"""软删/恢复、复制、移动。"""
from apps.audit.models import AuditLog
from apps.testcases.models import TestCase, TestCaseVersion
from apps.testcases.tests.base import NanoTestCase


class LifecycleTests(NanoTestCase):
    def test_soft_delete_filters_and_restore(self):
        keep = self.create_case(title="保留用例")
        gone = self.create_case(title="删除用例")

        response = self.client.delete(self.detail_url(gone["id"]))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["data"]["deleted"])

        self.assertEqual([case["id"] for case in self.list_cases()["items"]], [keep["id"]])
        self.assertEqual(TestCase.objects.filter(project=self.project).count(), 1)
        self.assertEqual(TestCase.all_objects.get(pk=gone["id"]).is_deleted, True)

        detail = self.client.get(self.detail_url(gone["id"]))
        self.assertEqual(detail.status_code, 404)
        self.assertEqual(detail.json()["code"], 40005)

        audit = AuditLog.objects.filter(object_type="testcase", object_id=gone["id"], action="delete")
        self.assertEqual(audit.count(), 1)

        restored = self.client.post(f"/api/v1/testcases/{gone['id']}/restore/")
        self.assertEqual(restored.status_code, 200, restored.content)
        self.assertEqual(restored.json()["data"]["title"], "删除用例")
        self.assertEqual(len(self.list_cases()["items"]), 2)
        self.assertEqual(self.client.get(self.detail_url(gone["id"])).status_code, 200)

    def test_restore_non_deleted_case_conflicts(self):
        case = self.create_case()
        response = self.client.post(f"/api/v1/testcases/{case['id']}/restore/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], 40007)

    def test_duplicate_copies_current_version_and_tags(self):
        source = self.create_case(
            title="下单支付",
            precondition="用户已登录",
            expected_result="支付成功",
            description="主流程",
            tag_ids=[self.tag_smoke.id],
            module_id=self.module.id,
        )
        # 再改一版，确认复制的是当前版本
        patched = self.patch_case(source["id"], {
            "updated_at": source["updated_at"],
            "steps": [{"action": "去结算", "expected": "进入收银台"}],
        })
        self.assertEqual(patched.status_code, 200, patched.content)

        response = self.client.post(f"/api/v1/testcases/{source['id']}/duplicate/")
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]

        self.assertNotEqual(data["case_key"], source["case_key"])
        self.assertEqual(data["title"], "下单支付副本")
        self.assertEqual(data["current_version"], 1)
        self.assertEqual(data["steps"], [{"order": 1, "action": "去结算", "expected": "进入收银台"}])
        self.assertEqual(data["expected_result"], "支付成功")
        self.assertEqual(data["precondition"], "用户已登录")
        self.assertEqual(data["module_id"], self.module.id)
        self.assertEqual([tag["id"] for tag in data["tags"]], [self.tag_smoke.id])
        self.assertEqual(data["creator"]["id"], self.user.id)

        new_case = TestCase.objects.get(pk=data["id"])
        self.assertEqual(TestCase.objects.filter(project=self.project).count(), 2)
        versions = TestCaseVersion.objects.filter(test_case=new_case)
        self.assertEqual(versions.count(), 1)
        self.assertEqual(versions[0].version, 1)
        self.assertEqual(versions[0].change_summary, f"复制自 {source['case_key']}")
        self.assertTrue(
            AuditLog.objects.filter(object_type="testcase", object_id=new_case.pk, action="create").exists()
        )

    def test_move_updates_module_and_audits(self):
        case = self.create_case(module_id=self.module.id)
        response = self.client.post(
            f"/api/v1/testcases/{case['id']}/move/", {"module_id": self.child_module.id}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual(data["module_id"], self.child_module.id)
        self.assertEqual([node["name"] for node in data["module_path"]], ["Auth", "Login", "Password"])

        audit = (
            AuditLog.objects.filter(object_type="testcase", object_id=case["id"], action="update")
            .order_by("-id")
            .first()
        )
        self.assertEqual(audit.new_data.get("module"), self.child_module.id)
        self.assertEqual(audit.old_data.get("module"), self.module.id)

        # 移动后按目标模块可筛选到
        moved = self.list_cases(module_id=self.child_module.id)
        self.assertEqual([item["id"] for item in moved["items"]], [case["id"]])

    def test_move_to_foreign_module_rejected(self):
        from apps.projects.models import Module, Project

        other_project = Project.objects.create(
            organization=self.org, name="Other", key="OTHR", owner=self.user
        )
        other_module = Module.objects.create(project=other_project, name="OtherModule")
        case = self.create_case()
        response = self.client.post(
            f"/api/v1/testcases/{case['id']}/move/", {"module_id": other_module.id}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], 40006)
