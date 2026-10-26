"""测试用例域（§11-13）：TestCase / TestCaseVersion / TestCaseTag。"""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from common.models import SoftDeleteModel


class TestCase(SoftDeleteModel):
    PRIORITY_CHOICES = [("P0", "P0"), ("P1", "P1"), ("P2", "P2"), ("P3", "P3")]
    TYPE_CHOICES = [
        ("functional", "功能"), ("regression", "回归"), ("smoke", "冒烟"),
        ("integration", "集成"), ("api", "接口"), ("ui", "UI"),
        ("performance", "性能"), ("security", "安全"), ("compatibility", "兼容"),
        ("exploratory", "探索"),
    ]
    STATUS_DRAFT, STATUS_ACTIVE, STATUS_DEPRECATED, STATUS_ARCHIVED = "draft", "active", "deprecated", "archived"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "草稿"), (STATUS_ACTIVE, "激活"),
        (STATUS_DEPRECATED, "废弃"), (STATUS_ARCHIVED, "归档"),
    ]
    AUTOMATION_CHOICES = [
        ("manual", "手工"), ("automated", "已自动化"),
        ("partial", "部分自动化"), ("not_automatable", "不可自动化"),
    ]

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="testcases")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="testcases")
    module = models.ForeignKey(
        "projects.Module", null=True, blank=True, on_delete=models.SET_NULL, related_name="testcases"
    )
    case_key = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    precondition = models.TextField(blank=True, default="")
    priority = models.CharField(max_length=2, choices=PRIORITY_CHOICES, default="P1")
    case_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default="functional")
    automation_status = models.CharField(max_length=16, choices=AUTOMATION_CHOICES, default="manual")
    automation_framework = models.CharField(max_length=64, blank=True, default="")
    automation_identifier = models.CharField(max_length=128, blank=True, default="")
    automation_script = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_testcases"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_testcases"
    )
    current_version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    sort_order = models.IntegerField(default=0)
    tags = models.ManyToManyField("projects.Tag", through="TestCaseTag", blank=True)

    class Meta:
        db_table = "testcases_testcase"
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["project", "module", "sort_order"]),
            models.Index(fields=["project", "priority"]),
            models.Index(fields=["project", "status"]),
            models.Index(fields=["project", "owner"]),
            models.Index(fields=["project", "updated_at"]),
            models.Index(fields=["case_key"]),
        ]

    def __str__(self):
        return f"{self.case_key} {self.title}"


class TestCaseVersion(models.Model):
    """用例版本快照：历史执行结果必须绑定版本（坑 4）。steps 为 JSONB：[{order,action,expected}]。"""

    test_case = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    precondition = models.TextField(blank=True, default="")
    steps = models.JSONField(default=list)
    expected_result = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="testcase_versions"
    )
    change_summary = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "testcases_version"
        unique_together = [("test_case", "version")]
        ordering = ["-version"]


class TestCaseTag(models.Model):
    test_case = models.ForeignKey(TestCase, on_delete=models.CASCADE)
    tag = models.ForeignKey("projects.Tag", on_delete=models.CASCADE)

    class Meta:
        db_table = "testcases_testcasetag"
        unique_together = [("test_case", "tag")]
