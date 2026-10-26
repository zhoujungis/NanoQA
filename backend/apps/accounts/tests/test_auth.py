"""登录 + /auth/me 权限清单测试。"""
from apps.accounts.tests.helpers import (
    NanoAPITestCase,
    bind_project,
    create_user,
    make_org,
    make_project,
)
from common.permissions import PERMISSION_CODENAMES

LOGIN_URL = "/api/v1/auth/login/"
ME_URL = "/api/v1/auth/me/"


class AuthMeTests(NanoAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user("alice", password="s3cret-pass")
        owner = create_user("owner")
        self.org = make_org(owner, slug="acme")
        self.project = make_project(self.org, owner, key="ACME")
        bind_project(self.user, self.project, "qa")

    def test_login_returns_tokens_and_user(self):
        resp = self.client.post(
            LOGIN_URL, {"email": "alice@example.com", "password": "s3cret-pass"}
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], 0)
        self.assertIn("access", body["data"])
        self.assertIn("refresh", body["data"])
        self.assertEqual(body["data"]["user"]["username"], "alice")

    def test_me_returns_permission_inventory(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(ME_URL)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        # qa 角色权限清单 + 项目成员关系
        self.assertIn("testcase.execute", data["permissions"])
        self.assertIn("testcase.create", data["permissions"])
        self.assertNotIn("user.manage", data["permissions"])
        self.assertFalse(data["is_system_admin"])
        memberships = {m["project_key"]: m["role"] for m in data["memberships"]}
        self.assertEqual(memberships["ACME"], "qa")

    def test_me_system_admin_gets_full_permissions(self):
        admin = create_user("root", is_system_admin=True)
        self.client.force_authenticate(admin)
        data = self.client.get(ME_URL).json()["data"]
        self.assertTrue(data["is_system_admin"])
        self.assertEqual(set(data["permissions"]), set(PERMISSION_CODENAMES))

    def test_me_requires_authentication(self):
        resp = self.client.get(ME_URL)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], 40002)
