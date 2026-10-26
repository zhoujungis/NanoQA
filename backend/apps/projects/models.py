"""项目域：Project / ProjectMember / Module / Tag / NumberSequence（§9.3、§10、§22、§49）。"""
from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from common.models import SoftDeleteModel, TimestampedModel

KEY_VALIDATOR = RegexValidator(r"^[A-Z][A-Z0-9]{1,15}$", "项目 Key 只能是 2-16 位大写字母或数字，且以字母开头")


class Project(TimestampedModel):
    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [(STATUS_ACTIVE, "进行中"), (STATUS_ARCHIVED, "已归档")]

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=128)
    key = models.CharField(max_length=16, validators=[KEY_VALIDATOR])
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_projects")

    class Meta:
        db_table = "projects_project"
        unique_together = [("organization", "key")]
        indexes = [
            models.Index(fields=["organization", "status"]),
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.key} {self.name}"


class ProjectMember(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships")
    role = models.ForeignKey("accounts.Role", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "projects_member"
        unique_together = [("project", "user")]

    def __str__(self):
        return f"{self.project.key}:{self.user.username}"


class Module(SoftDeleteModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="modules")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = "projects_module"
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["project", "parent", "sort_order"]),
        ]

    def __str__(self):
        return self.name


class Tag(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=64)
    color = models.CharField(max_length=16, default="#64748B")

    class Meta:
        db_table = "projects_tag"
        unique_together = [("project", "name")]


class NumberSequence(models.Model):
    """编号序列：select_for_update 取号，单调递增永不复用（§49）。"""

    ENTITY_TC = "TC"
    ENTITY_BUG = "BUG"
    ENTITY_REQ = "REQ"
    ENTITY_CHOICES = [(ENTITY_TC, "测试用例"), (ENTITY_BUG, "缺陷"), (ENTITY_REQ, "需求")]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="number_sequences")
    entity = models.CharField(max_length=8, choices=ENTITY_CHOICES)
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "projects_number_sequence"
        unique_together = [("project", "entity")]
