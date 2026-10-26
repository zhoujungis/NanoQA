"""缺陷域（§20-21）：Defect + 三张关联表。"""
from django.conf import settings
from django.db import models

from common.models import TimestampedModel


class Defect(TimestampedModel):
    SEVERITY_CHOICES = [
        ("Blocker", "致命"), ("Critical", "严重"), ("Major", "一般"),
        ("Minor", "次要"), ("Trivial", "轻微"),
    ]
    PRIORITY_CHOICES = [("P0", "P0"), ("P1", "P1"), ("P2", "P2"), ("P3", "P3")]
    STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_RESOLVED, STATUS_REOPENED = "Open", "In Progress", "Resolved", "Reopened"
    STATUS_CLOSED, STATUS_REJECTED, STATUS_DUPLICATE = "Closed", "Rejected", "Duplicate"
    STATUS_CHOICES = [
        (STATUS_OPEN, "打开"), (STATUS_IN_PROGRESS, "处理中"), (STATUS_RESOLVED, "已修复"),
        (STATUS_REOPENED, "重新打开"), (STATUS_CLOSED, "已关闭"),
        (STATUS_REJECTED, "已拒绝"), (STATUS_DUPLICATE, "重复"),
    ]

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="defects")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="defects")
    key = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default="Major")
    priority = models.CharField(max_length=2, choices=PRIORITY_CHOICES, default="P1")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN)
    environment = models.CharField(max_length=64, blank=True, default="")
    version = models.CharField(max_length=64, blank=True, default="")
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reported_defects"
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_defects"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    test_cases = models.ManyToManyField("testcases.TestCase", through="TestCaseDefect", blank=True)

    class Meta:
        db_table = "defects_defect"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["project", "priority"]),
            models.Index(fields=["project", "severity"]),
            models.Index(fields=["key"]),
        ]

    def __str__(self):
        return f"{self.key} {self.title}"


class TestCaseDefect(models.Model):
    test_case = models.ForeignKey("testcases.TestCase", on_delete=models.CASCADE)
    defect = models.ForeignKey(Defect, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "defects_testcase_defect"
        unique_together = [("test_case", "defect")]


class TestResultDefect(models.Model):
    test_result = models.ForeignKey("executions.TestResult", on_delete=models.CASCADE)
    defect = models.ForeignKey(Defect, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "defects_testresult_defect"
        unique_together = [("test_result", "defect")]


class RequirementDefect(models.Model):
    requirement = models.ForeignKey("requirements.Requirement", on_delete=models.CASCADE)
    defect = models.ForeignKey(Defect, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "defects_requirement_defect"
        unique_together = [("requirement", "defect")]
