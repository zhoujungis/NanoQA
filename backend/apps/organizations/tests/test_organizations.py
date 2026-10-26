"""组织 CRUD 测试：slug 唯一、可见性、乐观锁。"""
from apps.audit.models import AuditLog
from apps.accounts.tests.helpers import NanoAPITestCase, bind_org, create_user, make_org
from apps.organizations.models import Organization, OrganizationMember

ORG_URL = "/api/v1/organizations/"


class OrganizationTests(NanoAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user("alice")

    def test_create_organization_binds_owner_admin_and_audit(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(ORG_URL, {"name": "质量中心"})
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertEqual(data["owner"], self.user.id)
        self.assertTrue(data["slug"])

        org = Organization.objects.get(pk=data["id"])
        member = OrganizationMember.objects.get(organization=org, user=self.user)
        self.assertEqual(member.role.code, "admin")
        self.assertTrue(
            AuditLog.objects.filter(action="create", object_type="organization", object_id=org.pk).exists()
        )

    def test_slug_uniqueness(self):
        self.client.force_authenticate(self.user)
        self.client.post(ORG_URL, {"name": "Org A", "slug": "org-a"})
        resp = self.client.post(ORG_URL, {"name": "Org B", "slug": "org-a"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40007)

    def test_list_returns_only_my_organizations(self):
        mine = make_org(self.user, slug="mine")
        other = make_org(create_user("bob"), slug="other")
        bind_org(create_user("carol"), other, "qa")
        self.client.force_authenticate(self.user)
        ids = [o["id"] for o in self.client.get(ORG_URL).json()["data"]]
        self.assertIn(mine.id, ids)
        self.assertNotIn(other.id, ids)

    def test_non_member_forbidden(self):
        org = make_org(create_user("bob"), slug="other")
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{ORG_URL}{org.id}/")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], 40001)

    def test_missing_organization_40005(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{ORG_URL}999999/")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], 40005)

    def test_patch_requires_user_manage(self):
        org = make_org(self.user, slug="mine")
        qa = create_user("qa1")
        bind_org(qa, org, "qa")  # qa 角色无 user.manage
        self.client.force_authenticate(qa)
        resp = self.client.patch(f"{ORG_URL}{org.id}/", {"name": "改名"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], 40001)

    def test_patch_with_optimistic_lock(self):
        org = make_org(self.user, slug="mine")
        self.client.force_authenticate(self.user)
        detail = self.client.get(f"{ORG_URL}{org.id}/").json()["data"]

        resp = self.client.patch(
            f"{ORG_URL}{org.id}/",
            {"name": "新名字", "updated_at": detail["updated_at"]},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["name"], "新名字")
        self.assertTrue(
            AuditLog.objects.filter(action="update", object_type="organization", object_id=org.pk).exists()
        )

        # 旧 updated_at → 409 / 40003
        resp = self.client.patch(
            f"{ORG_URL}{org.id}/",
            {"name": "再改", "updated_at": detail["updated_at"]},
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["code"], 40003)
