"""需求 API 测试：编号生成 / CRUD / 筛选 / 乐观锁 / 软删。"""
from apps.audit.models import AuditLog
from apps.requirements.tests.base import NanoAPITestCase


class RequirementApiTests(NanoAPITestCase):
    def list_url(self):
        return f"/api/v1/projects/{self.project.pk}/requirements/"

    def detail_url(self, req):
        return f"/api/v1/requirements/{req.pk}/"

    # ---------------------------------------------------------------- 创建/编号
    def test_create_generates_sequential_req_keys(self):
        self.login(self.manager)
        r1 = self.client.post(self.list_url(), {"title": "用户登录"}, format="json")
        self.assertEqual(r1.status_code, 201)
        data = self.assertCode(r1, 0)
        self.assertEqual(data["key"], "SHOP-REQ-000001")
        self.assertEqual(data["status"], "draft")
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["creator"]["id"], self.manager.pk)

        r2 = self.client.post(self.list_url(), {"title": "订单支付"}, format="json")
        self.assertEqual(r2.status_code, 201)
        data2 = self.assertCode(r2, 0)
        self.assertEqual(data2["key"], "SHOP-REQ-000002")

        self.assertTrue(
            AuditLog.objects.filter(
                object_type="requirement", object_id=data["id"], action="create"
            ).exists()
        )

    def test_create_without_permission_denied(self):
        self.login(self.viewer)  # viewer 无 requirement.create
        r = self.client.post(self.list_url(), {"title": "x"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], 40001)

    def test_anonymous_unauthenticated(self):
        r = self.client.get(self.list_url())
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["code"], 40002)

    # ---------------------------------------------------------------- 列表筛选
    def test_list_filters(self):
        req_ready = self.make_requirement(title="登录功能", status="ready", priority="P0", owner=self.qa)
        self.make_requirement(title="下单功能", status="draft", priority="P1")
        self.login(self.qa)

        data = self.assertCode(self.client.get(self.list_url()), 0)
        self.assertEqual(data["total"], 2)

        data = self.assertCode(self.client.get(f"{self.list_url()}?status=ready"), 0)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["key"], req_ready.key)

        data = self.assertCode(self.client.get(f"{self.list_url()}?priority=P0"), 0)
        self.assertEqual(data["total"], 1)

        data = self.assertCode(self.client.get(f"{self.list_url()}?owner_id={self.qa.pk}"), 0)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["owner"]["id"], self.qa.pk)

        data = self.assertCode(self.client.get(f"{self.list_url()}?q=登录"), 0)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["key"], req_ready.key)

        data = self.assertCode(self.client.get(f"{self.list_url()}?q={req_ready.key}"), 0)
        self.assertEqual(data["total"], 1)

    # ---------------------------------------------------------------- 详情
    def test_retrieve_detail_summary(self):
        req = self.make_requirement()
        case1, case2 = self.make_testcase(), self.make_testcase()
        self.login(self.qa)
        self.assertCode(
            self.client.post(
                self.detail_url(req) + "testcases/", {"test_case_ids": [case1.pk, case2.pk]}, format="json"
            ),
            0,
        )
        run = self.make_run()
        self.make_result(run, case1, "passed")

        data = self.assertCode(self.client.get(self.detail_url(req)), 0)
        self.assertEqual(len(data["test_cases"]), 2)
        self.assertEqual(data["coverage"]["linked_cases"], 2)
        self.assertEqual(data["coverage"]["executed"], 1)
        self.assertEqual(data["coverage"]["passed"], 1)

    def test_retrieve_missing_requirement_404(self):
        self.login(self.qa)
        r = self.client.get("/api/v1/requirements/999999/")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["code"], 40005)

    # ---------------------------------------------------------------- 更新/乐观锁
    def test_update_with_optimistic_lock(self):
        req = self.make_requirement()
        self.login(self.manager)
        url = self.detail_url(req)

        r = self.client.patch(url, {"title": "新标题", "updated_at": req.updated_at.isoformat()}, format="json")
        data = self.assertCode(r, 0)
        self.assertEqual(data["title"], "新标题")

        # 原样回传响应里的 updated_at → 继续编辑成功
        r = self.client.patch(url, {"title": "第三版", "updated_at": data["updated_at"]}, format="json")
        self.assertCode(r, 0)

        # 回传旧值 → 409 / 40003
        r = self.client.patch(url, {"title": "冲突", "updated_at": req.updated_at.isoformat()}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["code"], 40003)

        # 缺 updated_at → 409 / 40003
        r = self.client.patch(url, {"title": "缺版本"}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["code"], 40003)

    def test_update_without_permission_denied(self):
        req = self.make_requirement()
        self.login(self.viewer)  # viewer 无 requirement.update
        r = self.client.patch(
            self.detail_url(req), {"title": "x", "updated_at": req.updated_at.isoformat()}, format="json"
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], 40001)

    # ---------------------------------------------------------------- 软删
    def test_soft_delete_filters_out(self):
        req = self.make_requirement()
        kept = self.make_requirement()
        self.login(self.manager)

        data = self.assertCode(self.client.delete(self.detail_url(req)), 0)
        self.assertTrue(data["deleted"])

        req.refresh_from_db()
        self.assertIsNotNone(req.deleted_at)

        data = self.assertCode(self.client.get(self.list_url()), 0)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["key"], kept.key)

        r = self.client.get(self.detail_url(req))
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["code"], 40005)

        self.assertTrue(
            AuditLog.objects.filter(object_type="requirement", object_id=req.pk, action="delete").exists()
        )

    def test_delete_without_permission_denied(self):
        req = self.make_requirement()
        self.login(self.qa)  # qa 无 requirement.delete
        r = self.client.delete(self.detail_url(req))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], 40001)
        req.refresh_from_db()
        self.assertIsNone(req.deleted_at)
