"""缺陷 API 测试：编号生成 / CRUD / 筛选 / 时间戳 / 乐观锁 / 归档权限。"""
from apps.audit.models import AuditLog
from apps.defects.models import RequirementDefect, TestCaseDefect
from apps.defects.tests.base import NanoAPITestCase


class DefectApiTests(NanoAPITestCase):
    def list_url(self):
        return f"/api/v1/projects/{self.project.pk}/defects/"

    def detail_url(self, defect):
        return f"/api/v1/defects/{defect.pk}/"

    # ---------------------------------------------------------------- 创建/编号
    def test_create_generates_sequential_bug_keys(self):
        self.login(self.qa)
        r1 = self.client.post(self.list_url(), {"title": "登录失败"}, format="json")
        self.assertEqual(r1.status_code, 201)
        data = self.assertCode(r1, 0)
        self.assertEqual(data["key"], "SHOP-BUG-000001")
        self.assertEqual(data["status"], "Open")
        self.assertEqual(data["reporter"]["id"], self.qa.pk)

        r2 = self.client.post(self.list_url(), {"title": "下单失败"}, format="json")
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(self.assertCode(r2, 0)["key"], "SHOP-BUG-000002")

        self.assertTrue(
            AuditLog.objects.filter(object_type="defect", object_id=data["id"], action="create").exists()
        )

    def test_create_with_links(self):
        case = self.make_testcase()
        requirement = self.make_requirement()
        self.login(self.qa)
        data = self.assertCode(
            self.client.post(
                self.list_url(),
                {
                    "title": "结算报错",
                    "severity": "Critical",
                    "priority": "P0",
                    "environment": "staging",
                    "version": "v1.2",
                    "assignee_id": self.manager.pk,
                    "test_case_ids": [case.pk],
                    "requirement_ids": [requirement.pk],
                },
                format="json",
            ),
            0,
        )
        self.assertEqual(data["severity"], "Critical")
        self.assertEqual(data["assignee"]["id"], self.manager.pk)
        self.assertTrue(TestCaseDefect.objects.filter(test_case=case, defect_id=data["id"]).exists())
        self.assertTrue(RequirementDefect.objects.filter(requirement=requirement, defect_id=data["id"]).exists())

    def test_create_without_permission_denied(self):
        self.login(self.viewer)  # viewer 无 defect.create
        r = self.client.post(self.list_url(), {"title": "x"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], 40001)

    # ---------------------------------------------------------------- 列表筛选
    def test_list_filters(self):
        bug1 = self.make_defect(title="登录超时", severity="Major", priority="P1", assignee=self.qa, status="Open")
        self.make_defect(title="支付乱码", severity="Minor", priority="P2", assignee=self.manager, status="Resolved")
        self.login(self.qa)

        data = self.assertCode(self.client.get(self.list_url()), 0)
        self.assertEqual(data["total"], 2)
        for field in ("key", "title", "status", "severity", "priority", "assignee", "reporter", "updated_at"):
            self.assertIn(field, data["items"][0])

        data = self.assertCode(self.client.get(f"{self.list_url()}?q=登录"), 0)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["key"], bug1.key)

        data = self.assertCode(self.client.get(f"{self.list_url()}?status=Resolved"), 0)
        self.assertEqual(data["total"], 1)

        data = self.assertCode(self.client.get(f"{self.list_url()}?severity=Minor"), 0)
        self.assertEqual(data["total"], 1)

        data = self.assertCode(self.client.get(f"{self.list_url()}?priority=P1"), 0)
        self.assertEqual(data["total"], 1)

        data = self.assertCode(self.client.get(f"{self.list_url()}?assignee_id={self.qa.pk}"), 0)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["assignee"]["id"], self.qa.pk)

        data = self.assertCode(self.client.get(f"{self.list_url()}?reporter_id={self.owner.pk}"), 0)
        self.assertEqual(data["total"], 2)

    # ---------------------------------------------------------------- 乐观锁
    def test_update_optimistic_lock(self):
        defect = self.make_defect()
        self.login(self.qa)
        url = self.detail_url(defect)

        r = self.client.patch(url, {"title": "新标题", "updated_at": defect.updated_at.isoformat()}, format="json")
        data = self.assertCode(r, 0)
        self.assertEqual(data["title"], "新标题")

        r = self.client.patch(url, {"title": "第三版", "updated_at": data["updated_at"]}, format="json")
        self.assertCode(r, 0)

        r = self.client.patch(url, {"title": "冲突", "updated_at": defect.updated_at.isoformat()}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["code"], 40003)

        r = self.client.patch(url, {"title": "缺版本"}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["code"], 40003)

    # ---------------------------------------------------------------- 时间戳自动维护
    def test_resolved_at_and_closed_at_auto_filled(self):
        defect = self.make_defect()
        self.login(self.qa)
        url = self.detail_url(defect)

        data = self.assertCode(
            self.client.patch(
                url, {"status": "In Progress", "updated_at": defect.updated_at.isoformat()}, format="json"
            ),
            0,
        )
        self.assertIsNone(data["resolved_at"])
        self.assertIsNone(data["closed_at"])

        data = self.assertCode(
            self.client.patch(url, {"status": "Resolved", "updated_at": data["updated_at"]}, format="json"), 0
        )
        self.assertIsNotNone(data["resolved_at"])
        self.assertIsNone(data["closed_at"])
        first_resolved_at = data["resolved_at"]

        data = self.assertCode(
            self.client.patch(url, {"status": "Closed", "updated_at": data["updated_at"]}, format="json"), 0
        )
        self.assertIsNotNone(data["closed_at"])

        # Closed → Reopened：清 closed_at，保留 resolved_at
        data = self.assertCode(
            self.client.patch(url, {"status": "Reopened", "updated_at": data["updated_at"]}, format="json"), 0
        )
        self.assertIsNone(data["closed_at"])
        self.assertEqual(data["resolved_at"], first_resolved_at)

        # 再次 Resolved：resolved_at 若已有则不覆盖
        data = self.assertCode(
            self.client.patch(url, {"status": "Resolved", "updated_at": data["updated_at"]}, format="json"), 0
        )
        self.assertEqual(data["resolved_at"], first_resolved_at)

    # ---------------------------------------------------------------- 归档（D9a）
    def test_delete_requires_system_admin(self):
        defect = self.make_defect()
        self.login(self.manager)  # admin 角色含 defect.delete，但非系统管理员
        r = self.client.delete(self.detail_url(defect))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], 40001)
        defect.refresh_from_db()
        self.assertEqual(defect.status, "Open")

    def test_system_admin_archive_sets_closed(self):
        defect = self.make_defect(status="In Progress")
        self.login(self.sysadmin)
        data = self.assertCode(self.client.delete(self.detail_url(defect)), 0)
        self.assertTrue(data["archived"])
        self.assertEqual(data["status"], "Closed")

        defect.refresh_from_db()
        self.assertEqual(defect.status, "Closed")
        self.assertIsNotNone(defect.closed_at)

        log = AuditLog.objects.get(object_type="defect", object_id=defect.pk, action="delete")
        self.assertTrue(log.new_data["archived"])
        self.assertEqual(log.new_data["status"], "Closed")

    def test_anonymous_unauthenticated(self):
        r = self.client.get(self.list_url())
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["code"], 40002)

    def test_retrieve_missing_defect_404(self):
        self.login(self.qa)
        r = self.client.get("/api/v1/defects/999999/")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["code"], 40005)
