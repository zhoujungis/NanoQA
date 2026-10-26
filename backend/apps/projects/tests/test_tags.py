"""标签 CRUD 测试：增改删、重名冲突、权限抽样。"""
from apps.accounts.tests.helpers import (
    NanoAPITestCase,
    bind_project,
    create_user,
    make_org,
    make_project,
)
from apps.audit.models import AuditLog
from apps.projects.models import Tag


class TagTests(NanoAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("owner")
        self.org = make_org(self.owner, slug="acme")
        self.project = make_project(self.org, self.owner, key="SHOP")
        self.base = f"/api/v1/projects/{self.project.id}/tags/"
        self.client.force_authenticate(self.owner)

    def test_tag_crud(self):
        resp = self.client.post(self.base, {"name": "smoke", "color": "#FF0000"})
        self.assertEqual(resp.status_code, 201)
        tag_id = resp.json()["data"]["id"]
        self.assertEqual(resp.json()["data"]["name"], "smoke")

        items = self.client.get(self.base).json()["data"]
        self.assertEqual([t["name"] for t in items], ["smoke"])

        resp = self.client.patch(f"/api/v1/tags/{tag_id}/", {"color": "#00FF00"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["color"], "#00FF00")
        self.assertTrue(
            AuditLog.objects.filter(action="update", object_type="tag", object_id=tag_id).exists()
        )

        resp = self.client.delete(f"/api/v1/tags/{tag_id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Tag.objects.filter(pk=tag_id).exists())
        self.assertTrue(
            AuditLog.objects.filter(action="delete", object_type="tag", object_id=tag_id).exists()
        )

    def test_duplicate_name_conflict(self):
        self.client.post(self.base, {"name": "smoke"})
        resp = self.client.post(self.base, {"name": "smoke"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], 40007)

    def test_permission_sample(self):
        tag = Tag.objects.create(project=self.project, name="regression")
        viewer = create_user("viewer1")
        bind_project(viewer, self.project, "viewer")
        self.client.force_authenticate(viewer)
        # viewer 只读
        self.assertEqual(self.client.get(self.base).status_code, 200)
        for resp in (
            self.client.post(self.base, {"name": "x"}),
            self.client.patch(f"/api/v1/tags/{tag.id}/", {"name": "y"}),
            self.client.delete(f"/api/v1/tags/{tag.id}/"),
        ):
            self.assertEqual(resp.status_code, 403)
            self.assertEqual(resp.json()["code"], 40001)

    def test_missing_tag_40005(self):
        resp = self.client.patch("/api/v1/tags/999999/", {"name": "x"})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], 40005)
