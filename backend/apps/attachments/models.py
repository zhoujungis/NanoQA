"""附件（§23）：DB 只存元数据。"""
from django.conf import settings
from django.db import models


class Attachment(models.Model):
    OBJECT_TYPES = ["testcase", "requirement", "defect", "testrun", "testresult"]

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="attachments")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="attachments")
    object_type = models.CharField(max_length=16, choices=[(t, t) for t in OBJECT_TYPES])
    object_id = models.BigIntegerField()
    filename = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=128)
    mime_type = models.CharField(max_length=128, blank=True, default="")
    size = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_attachments"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attachments_attachment"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["object_type", "object_id"])]
