"""审计日志（§24）：只追加，不修改不删除。"""
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class AuditLog(models.Model):
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_TRANSITION = "transition"
    ACTION_EXECUTE = "execute"
    ACTION_IMPORT = "import"
    ACTION_EXPORT = "export"
    ACTION_LINK = "link"
    ACTION_UNLINK = "unlink"
    ACTION_CHOICES = [
        (ACTION_CREATE, "创建"), (ACTION_UPDATE, "更新"), (ACTION_DELETE, "删除"),
        (ACTION_TRANSITION, "状态流转"), (ACTION_EXECUTE, "执行"), (ACTION_IMPORT, "导入"),
        (ACTION_EXPORT, "导出"), (ACTION_LINK, "关联"), (ACTION_UNLINK, "取消关联"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    object_type = models.CharField(max_length=32)
    object_id = models.BigIntegerField(null=True, blank=True)
    object_ref = models.CharField(max_length=64, blank=True, default="")
    old_data = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    new_data = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    request_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_auditlog"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["project", "created_at"]),
            models.Index(fields=["object_type", "object_id"]),
        ]
