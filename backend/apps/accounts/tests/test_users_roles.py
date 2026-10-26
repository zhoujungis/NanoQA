"""用户与角色管理 API 测试（user.manage / role.manage）。"""
from apps.accounts.models import Role
from apps.accounts.tests.helpers import (
    NanoAPITestCase,
    bind_project,
    create_user,
    make_org,
    make_project,
)

USERS_URL = "/api/v1/users/"
ROLES_URL = "/api/v1/roles/"


class UserListTests(NanoAPITestCase):
    def setUp(self):
        super().setUp()
        self.org = make_org(create_user("owner"), slug="acme")
        self.project = make_project(self.org, self.org.owner, key="ACME")
        self.viewer = create_user("viewer1")
        self.qa = create_user("qa1")
        self.pm = create_user("pm1")
        bind_project(self.viewer, self.project, "viewer")
        bind_project(self.qa, self.project, "qa")
        bind_project(self.pm, self.project, "pm")

    def test_permission_matrix(self):
        # viewer / qa 无 user.manage → 40001；pm 有 → 200
        for user in (self.viewer, self.qa):
            self.client.force_authenticate(user)
            resp = self.client.get(USERS_URL)
            self.assertEqual(resp.status_code, 403, user.username)
            self.assertEqual(resp.json()["code"], 40001, user.username)
        self.client.force_authenticate(self.pm)
        self.assertEqual(self.client.get(USERS_URL).status_code, 200)

    def test_list_is_paginated_and_supports_q(self):
        self.client.force_authenticate(self.pm)
        body = self.client.get(USERS_URL).json()["data"]
        self.assertEqual(body["total"], 4)
        self.assertIn("items", body)
        self.assertEqual(body["page"], 1)

        body = self.client.get(USERS_URL, {"q": "qa1"}).json()["data"]
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["username"], "qa1")

    def test_list_requires_authentication(self):
        resp = self.client.get(USERS_URL)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], 40002)


class RoleTests(NanoAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin = create_user("root", is_system_admin=True)
        self.qa = create_user("qa1")
        self.org = make_org(create_user("owner"), slug="acme")
        self.project = make_project(self.org, self.org.owner, key="ACME")
        bind_project(self.qa, self.project, "qa")

    def test_role_list_requires_authentication_only(self):
        resp = self.client.get(ROLES_URL)
        self.assertEqual(resp.status_code, 401)
        self.client.force_authenticate(self.qa)
        resp = self.client.get(ROLES_URL)
        self.assertEqual(resp.status_code, 200)
        codes = {r["code"] for r in resp.json()["data"]}
        self.assertTrue({"admin", "pm", "qa", "dev", "viewer"} <= codes)
        admin_role = next(r for r in resp.json()["data"] if r["code"] == "admin")
        self.assertIn("testcase.update", admin_role["permission_codenames"])

    def test_create_custom_role_requires_role_manage(self):
        payload = {"code": "triager", "name": "缺陷分诊", "permission_codenames": ["defect.update"]}
        self.client.force_authenticate(self.qa)
        resp = self.client.post(ROLES_URL, payload)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], 40001)

        self.client.force_authenticate(self.admin)
        resp = self.client.post(ROLES_URL, payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertEqual(data["code"], "triager")
        self.assertFalse(data["is_system"])
        self.assertEqual(data["permission_codenames"], ["defect.update"])

    def test_system_role_permission_change_forbidden(self):
        self.client.force_authenticate(self.admin)
        admin_role = Role.objects.get(code="admin")
        resp = self.client.patch(
            f"{ROLES_URL}{admin_role.id}/",
            {
                "permission_codenames": ["project.read"],
                "updated_at": self._updated_at(admin_role.id),
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40007)

    def test_custom_role_update_and_optimistic_lock(self):
        self.client.force_authenticate(self.admin)
        created = self.client.post(
            ROLES_URL,
            {"code": "helper", "name": "协作者", "permission_codenames": ["project.read"]},
        ).json()["data"]
        url = f"{ROLES_URL}{created['id']}/"

        resp = self.client.patch(
            url,
            {"name": "协作者V2", "permission_codenames": ["project.read", "defect.read"],
             "updated_at": created["updated_at"]},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["name"], "协作者V2")
        self.assertEqual(data["permission_codenames"], ["defect.read", "project.read"])

        # 旧版本 updated_at → 409 / 40003
        resp = self.client.patch(url, {"name": "冲突", "updated_at": created["updated_at"]})
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["code"], 40003)

    def _updated_at(self, role_id) -> str:
        roles = self.client.get(ROLES_URL).json()["data"]
        return next(r["updated_at"] for r in roles if r["id"] == role_id)
