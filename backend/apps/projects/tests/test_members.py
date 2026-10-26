"""项目成员管理测试：绑定 / 角色变更审计 / user.manage 权限矩阵。"""
from apps.accounts.tests.helpers import (
    NanoAPITestCase,
    bind_project,
    create_user,
    make_org,
    make_project,
    role,
)
from apps.audit.models import AuditLog
from apps.projects.models import ProjectMember


class ProjectMemberTests(NanoAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("owner")
        self.org = make_org(self.owner, slug="acme")
        self.project = make_project(self.org, self.owner, key="SHOP")
        self.member = create_user("member1")
        self.qa = create_user("qa1")
        bind_project(self.qa, self.project, "qa")
        self.base = f"/api/v1/projects/{self.project.id}/members/"

    def _add_member(self, user, role_code):
        self.client.force_authenticate(self.owner)
        return self.client.post(
            self.base, {"user_id": user.id, "role_id": role(role_code).id}
        )

    def test_add_member_writes_link_audit(self):
        resp = self._add_member(self.member, "dev")
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertEqual(data["user"]["username"], "member1")
        self.assertEqual(data["role"]["code"], "dev")
        self.assertTrue(
            AuditLog.objects.filter(action="link", object_type="projectmember", object_id=data["id"]).exists()
        )

    def test_role_change_writes_update_audit(self):
        member = ProjectMember.objects.create(
            project=self.project, user=self.member, role=role("qa")
        )
        self.client.force_authenticate(self.owner)
        resp = self.client.patch(
            f"/api/v1/projects/members/{member.id}/", {"role_id": role("pm").id}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["role"]["code"], "pm")
        log = AuditLog.objects.get(action="update", object_type="projectmember", object_id=member.id)
        self.assertEqual(log.old_data["role_code"], "qa")
        self.assertEqual(log.new_data["role_code"], "pm")

    def test_remove_member_writes_unlink_audit(self):
        member = ProjectMember.objects.create(
            project=self.project, user=self.member, role=role("qa")
        )
        self.client.force_authenticate(self.owner)
        resp = self.client.delete(f"/api/v1/projects/members/{member.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ProjectMember.objects.filter(pk=member.id).exists())
        self.assertTrue(
            AuditLog.objects.filter(action="unlink", object_type="projectmember", object_id=member.id).exists()
        )

    def test_qa_cannot_manage_members(self):
        member = ProjectMember.objects.create(
            project=self.project, user=self.member, role=role("viewer")
        )
        self.client.force_authenticate(self.qa)
        for resp in (
            self.client.get(self.base),
            self.client.post(self.base, {"user_id": self.owner.id, "role_id": role("qa").id}),
            self.client.patch(f"/api/v1/projects/members/{member.id}/", {"role_id": role("dev").id}),
            self.client.delete(f"/api/v1/projects/members/{member.id}/"),
        ):
            self.assertEqual(resp.status_code, 403)
            self.assertEqual(resp.json()["code"], 40001)

    def test_non_member_denied_with_40001(self):
        member = ProjectMember.objects.create(
            project=self.project, user=self.member, role=role("qa")
        )
        stranger = create_user("stranger")
        self.client.force_authenticate(stranger)
        resp = self.client.delete(f"/api/v1/projects/members/{member.id}/")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], 40001)

    def test_duplicate_member_conflict(self):
        self._add_member(self.member, "qa")
        resp = self._add_member(self.member, "dev")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40007)

    def test_member_of_another_org_role_rejected(self):
        from apps.accounts.models import Role

        other_org = make_org(create_user("bob"), slug="other")
        foreign_role = Role.objects.create(
            code="foreign-role", name="外部角色", organization=other_org, is_system=False
        )
        self.client.force_authenticate(self.owner)
        resp = self.client.post(
            self.base, {"user_id": self.member.id, "role_id": foreign_role.id}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40007)
