"""批量操作：update / move / tag / delete / restore，逐条审计与失败隔离。"""
from apps.audit.models import AuditLog
from apps.testcases.models import TestCase
from apps.testcases.tests.base import NanoTestCase


class BatchTests(NanoTestCase):
    def batch(self, op, ids, params=None):
        response = self.client.post(
            f"/api/v1/projects/{self.project.id}/testcases/batch/",
            {"op": op, "test_case_ids": ids, "params": params or {}},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["code"], 0)
        return body["data"]

    def test_batch_update_reports_succeeded_and_failed(self):
        first = self.create_case()
        second = self.create_case()
        result = self.batch("update", [first["id"], second["id"], 999999], {"priority": "P0", "status": "active"})

        self.assertEqual(result["succeeded"], [first["id"], second["id"]])
        self.assertEqual(len(result["failed"]), 1)
        self.assertEqual(result["failed"][0]["id"], 999999)
        self.assertIn("不存在", result["failed"][0]["reason"])

        for case_id in (first["id"], second["id"]):
            case = TestCase.objects.get(pk=case_id)
            self.assertEqual(case.priority, "P0")
            self.assertEqual(case.status, "active")

    def test_batch_update_invalid_transition_fails_single_item(self):
        ok_case = self.create_case()  # draft → draft 无变化，成功
        bad_case = self.create_case()
        TestCase.objects.filter(pk=bad_case["id"]).update(status="deprecated")
        result = self.batch("update", [ok_case["id"], bad_case["id"]], {"status": "draft"})

        # deprecated → draft 非法（40004），仅该条失败，其余不受影响
        self.assertEqual(result["succeeded"], [ok_case["id"]])
        self.assertEqual(result["failed"][0]["id"], bad_case["id"])
        self.assertEqual(TestCase.objects.get(pk=bad_case["id"]).status, "deprecated")

    def test_batch_update_rejects_unsupported_params(self):
        case = self.create_case()
        result = self.batch("update", [case["id"]], {"title": "不该允许"})
        self.assertEqual(result["succeeded"], [])
        self.assertEqual(result["failed"][0]["id"], case["id"])

    def test_batch_move(self):
        first = self.create_case()
        second = self.create_case()
        result = self.batch("move", [first["id"], second["id"], 424242], {"module_id": self.child_module.id})
        self.assertEqual(sorted(result["succeeded"]), sorted([first["id"], second["id"]]))
        self.assertEqual(result["failed"][0]["id"], 424242)
        self.assertEqual(TestCase.objects.get(pk=first["id"]).module_id, self.child_module.id)

    def test_batch_tag_add_and_remove(self):
        case = self.create_case(tag_ids=[self.tag_smoke.id])
        result = self.batch("tag", [case["id"]], {
            "add_tag_ids": [self.tag_fast.id],
            "remove_tag_ids": [self.tag_smoke.id],
        })
        self.assertEqual(result["succeeded"], [case["id"]])
        case_data = self.client.get(self.detail_url(case["id"])).json()["data"]
        self.assertEqual([tag["id"] for tag in case_data["tags"]], [self.tag_fast.id])
        self.assertTrue(
            AuditLog.objects.filter(object_type="testcase", object_id=case["id"]).exclude(action="create").exists()
        )

    def test_batch_delete_and_restore(self):
        first = self.create_case()
        second = self.create_case()

        deleted = self.batch("delete", [first["id"], second["id"]])
        self.assertEqual(sorted(deleted["succeeded"]), sorted([first["id"], second["id"]]))
        self.assertEqual(self.list_cases()["total"], 0)

        again = self.batch("delete", [first["id"]])
        self.assertEqual(again["failed"][0]["id"], first["id"])

        restored = self.batch("restore", [first["id"], second["id"]])
        self.assertEqual(sorted(restored["succeeded"]), sorted([first["id"], second["id"]]))
        self.assertEqual(self.list_cases()["total"], 2)

        twice = self.batch("restore", [first["id"]])
        self.assertEqual(twice["failed"][0]["id"], first["id"])

    def test_batch_invalid_op_rejected(self):
        case = self.create_case()
        response = self.client.post(
            f"/api/v1/projects/{self.project.id}/testcases/batch/",
            {"op": "rename", "test_case_ids": [case["id"]]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], 40006)
