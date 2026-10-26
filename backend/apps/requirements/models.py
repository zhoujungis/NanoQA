"""需求域（§14-15）。"""
from django.conf import settings
from django.db import models

from common.models import SoftDeleteModel


class Requirement(SoftDeleteModel):
    STATUS_DRAFT, STATUS_READY, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_CANCELLED = (
        "draft", "ready", "in_progress", "done", "cancelled"
    )
    STATUS_CHOICES = [
        (STATUS_DRAFT, "草稿"), (STATUS_READY, "就绪"), (STATUS_IN_PROGRESS, "进行中"),
        (STATUS_DONE, "完成"), (STATUS_CANCELLED, "取消"),
    ]
    PRIORITY_CHOICES = [("P0", "P0"), ("P1", "P1"), ("P2", "P2"), ("P3", "P3")]

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="requirements")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="requirements")
    key = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    priority = models.CharField(max_length=2, choices=PRIORITY_CHOICES, default="P1")
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_requirements"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_requirements"
    )
    version = models.PositiveIntegerField(default=1)
    test_cases = models.ManyToManyField("testcases.TestCase", through="RequirementTestCase", blank=True)

    class Meta:
        db_table = "requirements_requirement"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["key"]),
        ]

    def __str__(self):
        return f"{self.key} {self.title}"


class RequirementTestCase(models.Model):
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE)
    test_case = models.ForeignKey("testcases.TestCase", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "requirements_requirement_testcase"
        unique_together = [("requirement", "test_case")]
