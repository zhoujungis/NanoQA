"""账号域：User / Role / Permission（§3-4）。"""
from django.contrib.auth.models import AbstractUser
from django.db import models

from common.models import TimestampedModel
from common.permissions import PERMISSION_CODENAMES


class User(AbstractUser):
    display_name = models.CharField("显示名", max_length=64, blank=True, default="")
    avatar = models.URLField("头像", blank=True, default="")
    is_system_admin = models.BooleanField("系统管理员", default=False)

    class Meta:
        db_table = "accounts_user"
        ordering = ["id"]

    def __str__(self):
        return self.display_name or self.username


class Permission(models.Model):
    codename = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=64)
    group = models.CharField(max_length=32, default="general")

    class Meta:
        db_table = "accounts_permission"
        ordering = ["group", "codename"]

    def __str__(self):
        return self.codename


class Role(TimestampedModel):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    is_system = models.BooleanField(default=False)
    organization = models.ForeignKey(
        "organizations.Organization", null=True, blank=True,
        on_delete=models.CASCADE, related_name="custom_roles",
    )
    permissions = models.ManyToManyField(Permission, through="RolePermission", blank=True)

    class Meta:
        db_table = "accounts_role"
        ordering = ["id"]

    def __str__(self):
        return self.name


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        db_table = "accounts_role_permission"
        unique_together = [("role", "permission")]


SYSTEM_ROLES = {
    "admin": ("管理员", list(PERMISSION_CODENAMES)),
    "pm": ("项目负责人", [
        "project.read", "project.update",
        "requirement.read", "requirement.create", "requirement.update",
        "testcase.read", "testcase.create", "testcase.update", "testcase.review",
        "testplan.read", "testplan.create", "testplan.update", "testplan.delete", "testplan.execute",
        "defect.read", "defect.create", "defect.update",
        "report.read", "user.manage", "audit.read",
    ]),
    "qa": ("测试工程师", [
        "project.read",
        "requirement.read", "requirement.create", "requirement.update",
        "testcase.read", "testcase.create", "testcase.update", "testcase.delete",
        "testcase.execute", "testcase.review",
        "testplan.read", "testplan.create", "testplan.update", "testplan.execute",
        "defect.read", "defect.create", "defect.update",
        "report.read",
    ]),
    "dev": ("开发人员", [
        "project.read",
        "requirement.read",
        "testcase.read",
        "defect.read", "defect.update",
        "report.read",
    ]),
    "viewer": ("只读用户", [
        "project.read", "requirement.read", "testcase.read",
        "testplan.read", "defect.read", "report.read",
    ]),
}
