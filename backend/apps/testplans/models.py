"""测试计划域（§16-17）。"""
from django.conf import settings
from django.db import models

from common.models import TimestampedModel


class TestPlan(TimestampedModel):
    STATUS_DRAFT, STATUS_READY, STATUS_RUNNING, STATUS_COMPLETED, STATUS_CANCELLED = (
        "draft", "ready", "running", "completed", "cancelled"
    )
    STATUS_CHOICES = [
        (STATUS_DRAFT, "草稿"), (STATUS_READY, "就绪"), (STATUS_RUNNING, "执行中"),
        (STATUS_COMPLETED, "已完成"), (STATUS_CANCELLED, "已取消"),
    ]

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="testplans")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="testplans")
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    version = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_testplans"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_testplans"
    )

    class Meta:
        db_table = "testplans_testplan"
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["project", "status"])]


class TestPlanCase(models.Model):
    EXECUTION_STATUS_CHOICES = [
        ("not_run", "未执行"), ("passed", "通过"), ("failed", "失败"),
        ("blocked", "阻塞"), ("skipped", "跳过"),
    ]

    test_plan = models.ForeignKey(TestPlan, on_delete=models.CASCADE, related_name="plan_cases")
    test_case = models.ForeignKey("testcases.TestCase", on_delete=models.CASCADE, related_name="plan_links")
    priority = models.CharField(max_length=2, blank=True, default="")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_plan_cases"
    )
    execution_status = models.CharField(max_length=16, choices=EXECUTION_STATUS_CHOICES, default="not_run")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "testplans_testplancase"
        unique_together = [("test_plan", "test_case")]
