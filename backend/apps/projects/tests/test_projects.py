"""项目 API 测试：创建 / key 校验 / 可见性 / 乐观锁 / 归档软删。"""
from apps.accounts.tests.helpers import (
    NanoAPITestCase,
    bind_org,
    bind_project,
    create_user,
    make_org,
    make_project,
)
from apps.audit.models import AuditLog
from apps.projects.models import Project, ProjectMember

PROJECTS_URL = "/api/v1/projects/"


class ProjectCreateTests(NanoAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("owner")
        self.org = make_org(self.owner, slug="acme")

    def test_create_project_binds_creator_admin_and_audit(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.post(
            PROJECTS_URL,
            {"name": "商城测试", "key": "SHOP", "organization_id": self.org.id},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertEqual(data["key"], "SHOP")
        self.assertEqual(data["role"], "admin")

        project = Project.objects.get(pk=data["id"])
        member = ProjectMember.objects.get(project=project, user=self.owner)
        self.assertEqual(member.role.code, "admin")
        self.assertTrue(
            AuditLog.objects.filter(action="create", object_type="project", object_id=project.pk).exists()
        )

    def test_create_without_organization_uses_default_org(self):
        admin = create_user("root", is_system_admin=True)
        self.client.force_authenticate(admin)
        resp = self.client.post(PROJECTS_URL, {"name": "个人项目", "key": "MYPROJ"})
        self.assertEqual(resp.status_code, 201)
        project = Project.objects.get(pk=resp.json()["data"]["id"])
        self.assertEqual(project.organization.slug, f"user-{admin.id}")
        self.assertEqual(project.organization.owner, admin)

    def test_viewer_cannot_create_project(self):
        viewer = create_user("viewer1")
        bind_org(viewer, self.org, "viewer")
        self.client.force_authenticate(viewer)
        resp = self.client.post(
            PROJECTS_URL, {"name": "X", "key": "XPJT", "organization_id": self.org.id}
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], 40001)
        # 无 organization_id（默认组织兜底）同样拒绝
        resp = self.client.post(PROJECTS_URL, {"name": "X", "key": "XPJT"})
        self.assertEqual(resp.json()["code"], 40001)
        self.assertFalse(Project.objects.exists())

    def test_non_member_cannot_create_in_foreign_org(self):
        stranger = create_user("stranger")
        make_org(stranger, slug="stranger-org")  # 拥有自己的组织（全局有 project.create）
        self.client.force_authenticate(stranger)
        resp = self.client.post(
            PROJECTS_URL, {"name": "X", "key": "XORG", "organization_id": self.org.id}
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], 40001)

    def test_key_conflict_and_format(self):
        make_project(self.org, self.owner, key="SHOP")
        self.client.force_authenticate(self.owner)
        resp = self.client.post(
            PROJECTS_URL, {"name": "重复", "key": "SHOP", "organization_id": self.org.id}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40007)

        resp = self.client.post(
            PROJECTS_URL, {"name": "小写", "key": "shop", "organization_id": self.org.id}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40006)


class ProjectListTests(NanoAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("owner")
        self.org = make_org(self.owner, slug="acme")
        self.p1 = make_project(self.org, self.owner, key="ALPHA", name="阿尔法")
        self.p2 = make_project(self.org, self.owner, key="BETA", name="贝塔")
        self.p2.status = Project.STATUS_ARCHIVED
        self.p2.save(update_fields=["status", "updated_at"])
        self.member = create_user("member1")
        bind_project(self.member, self.p1, "qa")

    def test_visibility_and_role(self):
        self.client.force_authenticate(self.member)
        data = self.client.get(PROJECTS_URL).json()["data"]
        self.assertEqual([p["key"] for p in data["items"]], ["ALPHA"])
        self.assertEqual(data["items"][0]["role"], "qa")
        self.assertEqual(data["total"], 1)

        # 系统管理员看全部
        admin = create_user("root", is_system_admin=True)
        self.client.force_authenticate(admin)
        data = self.client.get(PROJECTS_URL).json()["data"]
        self.assertEqual(data["total"], 2)
        self.assertIsNone(data["items"][0]["role"])

    def test_search_and_status_filter(self):
        self.client.force_authenticate(self.owner)
        data = self.client.get(PROJECTS_URL, {"q": "ALP"}).json()["data"]
        self.assertEqual(data["total"], 1)
        data = self.client.get(PROJECTS_URL, {"status": "archived"}).json()["data"]
        self.assertEqual([p["key"] for p in data["items"]], ["BETA"])


class ProjectDetailTests(NanoAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("owner")
        self.org = make_org(self.owner, slug="acme")
        self.project = make_project(self.org, self.owner, key="SHOP")
        self.stranger = create_user("stranger")

    def test_non_member_denied(self):
        self.client.force_authenticate(self.stranger)
        resp = self.client.get(f"{PROJECTS_URL}{self.project.id}/")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], 40001)

    def test_missing_project_40005(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.get(f"{PROJECTS_URL}999999/")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], 40005)

    def test_patch_with_optimistic_lock(self):
        self.client.force_authenticate(self.owner)
        detail = self.client.get(f"{PROJECTS_URL}{self.project.id}/").json()["data"]

        resp = self.client.patch(
            f"{PROJECTS_URL}{self.project.id}/",
            {"description": "v2", "updated_at": detail["updated_at"]},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["description"], "v2")
        log = AuditLog.objects.get(action="update", object_type="project", object_id=self.project.id)
        self.assertEqual(log.old_data["description"], "")
        self.assertEqual(log.new_data["description"], "v2")

        # 旧 updated_at → 409 / 40003
        resp = self.client.patch(
            f"{PROJECTS_URL}{self.project.id}/",
            {"description": "v3", "updated_at": detail["updated_at"]},
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["code"], 40003)

    def test_key_immutable_after_create(self):
        self.client.force_authenticate(self.owner)
        detail = self.client.get(f"{PROJECTS_URL}{self.project.id}/").json()["data"]
        resp = self.client.patch(
            f"{PROJECTS_URL}{self.project.id}/",
            {"key": "OTHER", "updated_at": detail["updated_at"]},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40006)

    def test_delete_archives_without_physical_delete(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.delete(f"{PROJECTS_URL}{self.project.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["status"], "archived")
        self.assertTrue(Project.objects.filter(pk=self.project.id).exists())
        self.assertTrue(
            AuditLog.objects.filter(action="delete", object_type="project", object_id=self.project.id).exists()
        )

    def test_delete_requires_project_delete_permission(self):
        qa = create_user("qa1")
        bind_project(qa, self.project, "qa")
        self.client.force_authenticate(qa)
        resp = self.client.delete(f"{PROJECTS_URL}{self.project.id}/")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], 40001)
