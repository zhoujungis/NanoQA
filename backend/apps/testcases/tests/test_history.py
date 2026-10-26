"""版本历史与审计历史端点。"""
from apps.testcases.tests.base import NanoTestCase


class VersionAndHistoryTests(NanoTestCase):
    def test_versions_list(self):
        created = self.create_case(title="V1 标题")
        self.patch_case(created["id"], {
            "updated_at": created["updated_at"],
            "title": "V2 标题",
            "change_summary": "改标题",
        })

        response = self.client.get(f"/api/v1/testcases/{created['id']}/versions/")
        self.assertEqual(response.status_code, 200, response.content)
        items = response.json()["data"]["items"]
        self.assertEqual([item["version"] for item in items], [2, 1])
        self.assertEqual(items[0]["title"], "V2 标题")
        self.assertEqual(items[0]["change_summary"], "改标题")
        self.assertEqual(items[0]["created_by"]["id"], self.user.id)
        self.assertEqual(items[1]["change_summary"], "初始版本")
        for item in items:
            self.assertEqual(set(item), {"id", "version", "title", "change_summary", "created_by", "created_at"})

    def test_version_detail_returns_full_steps(self):
        created = self.create_case(steps=[{"action": "第一步", "expected": "ok"}, {"action": "第二步", "expected": "ok"}])
        versions = self.client.get(f"/api/v1/testcases/{created['id']}/versions/").json()["data"]["items"]
        version_id = versions[0]["id"]

        response = self.client.get(f"/api/v1/testcase-versions/{version_id}/")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["test_case"], created["id"])
        self.assertEqual(
            data["steps"],
            [
                {"order": 1, "action": "第一步", "expected": "ok"},
                {"order": 2, "action": "第二步", "expected": "ok"},
            ],
        )
        self.assertEqual(data["expected_result"], "")
        self.assertEqual(data["change_summary"], "初始版本")

    def test_version_detail_not_found(self):
        response = self.client.get("/api/v1/testcase-versions/999999/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], 40005)

    def test_history_returns_paginated_audit_logs(self):
        created = self.create_case(title="审计标题")
        self.patch_case(created["id"], {"updated_at": created["updated_at"], "title": "审计标题 2"})
        self.client.delete(self.detail_url(created["id"]))

        response = self.client.get(f"/api/v1/testcases/{created['id']}/history/")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual(set(data), {"items", "total", "page", "page_size"})
        self.assertEqual(data["total"], 3)
        actions = [item["action"] for item in data["items"]]
        self.assertEqual(actions, ["delete", "update", "create"])
        self.assertEqual(data["items"][0]["object_type"], "testcase")
        self.assertEqual(data["items"][0]["object_ref"], created["case_key"])

        # 分页参数生效
        page2 = self.client.get(f"/api/v1/testcases/{created['id']}/history/", {"page": 2, "page_size": 1}).json()["data"]
        self.assertEqual(page2["page"], 2)
        self.assertEqual(len(page2["items"]), 1)
