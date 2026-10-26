"""附件全链路：mime/size 拒绝、上传/下载/删除、列表过滤（MEDIA_ROOT 指向临时目录）。"""
import shutil
import tempfile
from pathlib import Path
from urllib.parse import quote

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.attachments.models import Attachment
from apps.attachments.tests import helpers
from apps.audit.models import AuditLog


class AttachmentApiTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_dir = tempfile.mkdtemp()
        cls._override = override_settings(MEDIA_ROOT=cls.media_dir, ATTACHMENT_MAX_SIZE=1024)
        cls._override.enable()
        cls.addClassCleanup(cls._override.disable)
        cls.addClassCleanup(shutil.rmtree, cls.media_dir, ignore_errors=True)

    def setUp(self):
        self.user = helpers.make_user()
        self.project = helpers.make_project(self.user)
        self.case = helpers.make_case(self.project, self.user)
        self.client.force_authenticate(self.user)
        # 审计落库需要 User-Agent（audit.user_agent 非空列）
        self.client.credentials(HTTP_USER_AGENT="nanoqa-tests")

    def _upload(self, filename="测试报告.png", content=b"png-bytes", content_type="image/png", **extra):
        payload = {
            "file": SimpleUploadedFile(filename, content, content_type=content_type),
            "object_type": "testcase",
            "object_id": self.case.id,
            "project_id": self.project.id,
        }
        payload.update(extra)
        return self.client.post("/api/v1/attachments/", payload, format="multipart")

    def _storage_path(self, storage_key: str) -> Path:
        return Path(self.media_dir) / "attachments" / storage_key

    def test_upload_success(self):
        response = self._upload()
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["filename"], "测试报告.png")
        self.assertEqual(data["mime_type"], "image/png")
        self.assertEqual(data["size"], len(b"png-bytes"))
        self.assertEqual(data["object_type"], "testcase")
        self.assertEqual(data["object_id"], self.case.id)

        attachment = Attachment.objects.get(pk=data["id"])
        self.assertEqual(attachment.uploaded_by_id, self.user.id)
        self.assertEqual(attachment.organization_id, self.project.organization_id)
        self.assertTrue(self._storage_path(attachment.storage_key).exists())
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.ACTION_CREATE, object_type="attachment").exists()
        )

    def test_reject_disallowed_mime(self):
        response = self._upload(filename="evil.exe", content=b"MZ", content_type="application/x-msdownload")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], 40006)
        self.assertEqual(Attachment.objects.count(), 0)

    def test_reject_oversized_file(self):
        response = self._upload(filename="big.png", content=b"x" * 2048, content_type="image/png")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], 40006)
        self.assertEqual(Attachment.objects.count(), 0)

    def test_reject_object_of_other_project(self):
        other_user = helpers.make_user(username="other")
        other_project = helpers.make_project(other_user, key="OTHER")
        other_case = helpers.make_case(other_project, other_user, title="他项目用例")

        # 对象属于 other_project，但 body 声明本项目 → 拒绝
        response = self._upload(object_id=other_case.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], 40006)
        self.assertEqual(Attachment.objects.count(), 0)

    def test_download_with_rfc5987_filename(self):
        filename = "测试报告.png"
        content = b"png-bytes"
        attachment_id = self._upload(filename=filename, content=content).json()["data"]["id"]

        response = self.client.get(f"/api/v1/attachments/{attachment_id}/download/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), content)
        disposition = response["Content-Disposition"]
        self.assertIn("attachment", disposition)
        self.assertIn("filename*=utf-8''", disposition.lower())
        self.assertIn(quote(filename), disposition)

    def test_delete_removes_file_and_metadata(self):
        attachment_id = self._upload().json()["data"]["id"]
        storage_key = Attachment.objects.get(pk=attachment_id).storage_key
        self.assertTrue(self._storage_path(storage_key).exists())

        response = self.client.delete(f"/api/v1/attachments/{attachment_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["deleted"])
        self.assertEqual(Attachment.objects.count(), 0)
        self.assertFalse(self._storage_path(storage_key).exists())
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.ACTION_DELETE, object_type="attachment").exists()
        )

    def test_list_filter_by_object(self):
        self._upload(filename="a.png")
        self._upload(filename="b.png")
        other_case = helpers.make_case(self.project, self.user, title="另一个用例")
        self._upload(filename="c.png", object_id=other_case.id)

        response = self.client.get(
            f"/api/v1/projects/{self.project.id}/attachments/?object_type=testcase&object_id={other_case.id}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["filename"], "c.png")

        all_response = self.client.get(f"/api/v1/projects/{self.project.id}/attachments/")
        self.assertEqual(all_response.json()["data"]["total"], 3)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(f"/api/v1/projects/{self.project.id}/attachments/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], 40002)
