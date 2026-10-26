"""模块树测试：树构建 / 移动（环检测）/ 删除保护 / 软删过滤 / 乐观锁。"""
from apps.accounts.tests.helpers import (
    NanoAPITestCase,
    bind_project,
    create_user,
    make_org,
    make_project,
)
from apps.audit.models import AuditLog
from apps.projects.models import Module
from apps.testcases.models import TestCase


class ModuleTreeTests(NanoAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("owner")
        self.org = make_org(self.owner, slug="acme")
        self.project = make_project(self.org, self.owner, key="SHOP")
        self.base = f"/api/v1/projects/{self.project.id}/modules/"
        self.client.force_authenticate(self.owner)
        self.root = self._create("购物车")
        self.child = self._create("结算", parent_id=self.root["id"])
        self.other = self._create("搜索")

    def _create(self, name, parent_id=None, sort_order=0):
        payload = {"name": name, "sort_order": sort_order}
        if parent_id is not None:
            payload["parent_id"] = parent_id
        resp = self.client.post(self.base, payload)
        self.assertEqual(resp.status_code, 201)
        return resp.json()["data"]

    def _tree(self):
        return self.client.get(self.base).json()["data"]

    def test_tree_nesting_and_case_count(self):
        TestCase.objects.create(
            organization=self.org, project=self.project, module_id=self.child["id"],
            case_key="SHOP-TC-000001", title="正常结算", creator=self.owner,
        )
        TestCase.objects.create(
            organization=self.org, project=self.project, module_id=self.child["id"],
            case_key="SHOP-TC-000002", title="优惠券结算", creator=self.owner,
        )
        tree = self._tree()
        self.assertEqual([n["name"] for n in tree], ["购物车", "搜索"])
        cart = tree[0]
        self.assertEqual(cart["parent_id"], None)
        self.assertEqual(cart["case_count"], 0)
        self.assertEqual([c["name"] for c in cart["children"]], ["结算"])
        settle = cart["children"][0]
        self.assertEqual(settle["parent_id"], cart["id"])
        self.assertEqual(settle["case_count"], 2)
        self.assertIn("description", settle)
        self.assertIn("sort_order", settle)

    def test_move_module_and_cycle_detection(self):
        url = f"/api/v1/modules/{self.root['id']}/move/"
        # 移到另一个根下
        resp = self.client.post(url, {"parent_id": self.other["id"], "sort_order": 5})
        self.assertEqual(resp.status_code, 200)
        tree = self._tree()
        self.assertEqual([n["name"] for n in tree], ["搜索"])
        self.assertEqual(tree[0]["children"][0]["name"], "购物车")

        # 移到自己的子孙下 → 业务冲突
        resp = self.client.post(url, {"parent_id": self.child["id"]})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40007)
        # 移到自己 → 同样冲突
        resp = self.client.post(url, {"parent_id": self.root["id"]})
        self.assertEqual(resp.json()["code"], 40007)

        # 移回根部
        resp = self.client.post(url, {"parent_id": None, "sort_order": 0})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self._tree()), 2)

    def test_move_to_missing_parent_40005(self):
        resp = self.client.post(
            f"/api/v1/modules/{self.root['id']}/move/", {"parent_id": 999999}
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], 40005)

    def test_delete_protection(self):
        # 有子模块 → 禁删
        resp = self.client.delete(f"/api/v1/modules/{self.root['id']}/")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40007)
        self.assertEqual(resp.json()["message"], "模块下存在子模块或测试用例，禁止删除")

        # 有测试用例（含软删）→ 禁删
        case = TestCase.objects.create(
            organization=self.org, project=self.project, module_id=self.child["id"],
            case_key="SHOP-TC-000001", title="用例", creator=self.owner,
        )
        self.client.delete(f"/api/v1/modules/{self.child['id']}/")
        case.soft_delete()
        resp = self.client.delete(f"/api/v1/modules/{self.child['id']}/")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40007)

        # 清空用例后可删（软删 + 审计 + 树过滤）
        case.delete()
        resp = self.client.delete(f"/api/v1/modules/{self.child['id']}/")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(Module.objects.filter(pk=self.child["id"]).first())
        self.assertIsNotNone(Module.all_objects.filter(pk=self.child["id"]).first())
        self.assertEqual(self._tree()[0]["children"], [])
        self.assertTrue(
            AuditLog.objects.filter(action="delete", object_type="module", object_id=self.child["id"]).exists()
        )

    def test_patch_with_optimistic_lock(self):
        url = f"/api/v1/modules/{self.root['id']}/"
        detail = self.client.get(self.base).json()["data"][0]
        resp = self.client.patch(url, {"name": "新购物车", "updated_at": detail["updated_at"]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["name"], "新购物车")

        resp = self.client.patch(url, {"name": "冲突", "updated_at": detail["updated_at"]})
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["code"], 40003)

    def test_permission_matrix_sample(self):
        viewer = create_user("viewer1")
        bind_project(viewer, self.project, "viewer")
        self.client.force_authenticate(viewer)
        # viewer 可读树
        self.assertEqual(self.client.get(self.base).status_code, 200)
        # viewer 不能建/改/删模块
        resp = self.client.post(self.base, {"name": "X"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], 40001)
        resp = self.client.patch(f"/api/v1/modules/{self.root['id']}/", {"name": "X"})
        self.assertEqual(resp.json()["code"], 40001)
        resp = self.client.delete(f"/api/v1/modules/{self.root['id']}/")
        self.assertEqual(resp.json()["code"], 40001)

        # 非成员 → 40001
        stranger = create_user("stranger")
        self.client.force_authenticate(stranger)
        resp = self.client.get(self.base)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], 40001)
