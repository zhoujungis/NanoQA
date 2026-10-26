"""测试执行域（§18-19）：TestRun / TestResult。"""
from django.conf import settings
from django.db import models

from common.models import TimestampedModel


class TestRun(TimestampedModel):
    STATUS_CREATED, STATUS_RUNNING, STATUS_FINISHED, STATUS_CANCELLED = "created", "running", "finished", "cancelled"
    STATUS_CHOICES = [
        (STATUS_CREATED, "已创建"), (STATUS_RUNNING, "执行中"),
        (STATUS_FINISHED, "已完成"), (STATUS_CANCELLED, "已取消"),
    ]

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="testruns")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="testruns")
    test_plan = models.ForeignKey("testplans.TestPlan", on_delete=models.CASCADE, related_name="runs")
    name = models.CharField(max_length=128)
    environment = models.CharField(max_length=64, blank=True, default="")
    build_version = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_CREATED)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_testruns"
    )

    class Meta:
        db_table = "executions_testrun"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["project", "status"])]


class TestResult(models.Model):
    STATUS_CHOICES = [
        ("passed", "通过"), ("failed", "失败"), ("blocked", "阻塞"),
        ("skipped", "跳过"), ("not_run", "未执行"),
    ]

    test_run = models.ForeignKey(TestRun, on_delete=models.CASCADE, related_name="results")
    test_case = models.ForeignKey("testcases.TestCase", on_delete=models.CASCADE, related_name="results")
    # 坑 4：结果必须绑定执行时的用例版本快照
    test_case_version = models.ForeignKey(
        "testcases.TestCaseVersion", on_delete=models.PROTECT, related_name="results"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="not_run")
    actual_result = models.TextField(blank=True, default="")
    comment = models.TextField(blank=True, default="")
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="executed_results"
    )
    executed_at = models.DateTimeField(null=True, blank=True)
    duration = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "executions_testresult"
        unique_together = [("test_run", "test_case")]
        ordering = ["id"]
        indexes = [
            models.Index(fields=["test_run", "status"]),
            models.Index(fields=["test_case", "status"]),
        ]
