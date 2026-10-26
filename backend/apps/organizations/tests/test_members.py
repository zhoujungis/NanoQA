"""组织成员管理测试：绑定 / 角色变更审计 / user.manage 权限。"""
from apps.accounts.tests.helpers import NanoAPITestCase, bind_org, create_user, make_org, role
from apps.audit.models import AuditLog
from apps.organizations.models import OrganizationMember


class OrganizationMemberTests(NanoAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("owner")
        self.org = make_org(self.owner, slug="acme")
        self.member = create_user("member1")
        self.qa = create_user("qa1")
        bind_org(self.qa, self.org, "qa")
        self.base = f"/api/v1/organizations/{self.org.id}/members/"

    def _add_member(self, user, role_code):
        self.client.force_authenticate(self.owner)
        return self.client.post(
            self.base, {"user_id": user.id, "role_id": role(role_code).id}
        )

    def test_add_member_writes_link_audit(self):
        resp = self._add_member(self.member, "qa")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["data"]["user"]["username"], "member1")
        self.assertEqual(resp.json()["data"]["role"]["code"], "qa")
        self.assertTrue(
            AuditLog.objects.filter(
                action="link", object_type="organizationmember",
                object_id=resp.json()["data"]["id"],
            ).exists()
        )

    def test_role_change_writes_update_audit(self):
        member = OrganizationMember.objects.create(
            organization=self.org, user=self.member, role=role("qa")
        )
        self.client.force_authenticate(self.owner)
        resp = self.client.patch(
            f"/api/v1/organizations/members/{member.id}/",
            {"role_id": role("dev").id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["role"]["code"], "dev")
        log = AuditLog.objects.get(action="update", object_type="organizationmember", object_id=member.id)
        self.assertEqual(log.old_data["role_code"], "qa")
        self.assertEqual(log.new_data["role_code"], "dev")

    def test_remove_member_writes_unlink_audit(self):
        member = OrganizationMember.objects.create(
            organization=self.org, user=self.member, role=role("qa")
        )
        self.client.force_authenticate(self.owner)
        resp = self.client.delete(f"/api/v1/organizations/members/{member.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(OrganizationMember.objects.filter(pk=member.id).exists())
        self.assertTrue(
            AuditLog.objects.filter(action="unlink", object_type="organizationmember", object_id=member.id).exists()
        )

    def test_qa_cannot_manage_members(self):
        member = OrganizationMember.objects.create(
            organization=self.org, user=self.member, role=role("viewer")
        )
        self.client.force_authenticate(self.qa)
        resp = self.client.get(self.base)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], 40001)
        resp = self.client.post(self.base, {"user_id": self.owner.id, "role_id": role("qa").id})
        self.assertEqual(resp.json()["code"], 40001)
        resp = self.client.patch(
            f"/api/v1/organizations/members/{member.id}/", {"role_id": role("dev").id}
        )
        self.assertEqual(resp.json()["code"], 40001)
        resp = self.client.delete(f"/api/v1/organizations/members/{member.id}/")
        self.assertEqual(resp.json()["code"], 40001)

    def test_duplicate_member_conflict(self):
        self._add_member(self.member, "qa")
        resp = self._add_member(self.member, "dev")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40007)
