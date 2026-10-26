"""审计服务：与业务写入同一事务调用（§51）。"""
import logging

from apps.audit.models import AuditLog
from common.utils import client_ip, user_agent

logger = logging.getLogger("nanoqa.audit")


class AuditService:
    @staticmethod
    def record(action: str, obj, *, request=None, user=None, old_data=None, new_data=None,
               object_ref: str = "", project=None, organization=None):
        """记录一条审计。obj 可为模型实例（取 type/id）或 (object_type, object_id)。"""
        if isinstance(obj, tuple):
            object_type, object_id = obj
        else:
            object_type = obj.__class__.__name__.lower()
            object_id = obj.pk
            if not object_ref:
                object_ref = getattr(obj, "case_key", None) or getattr(obj, "key", None) or getattr(obj, "name", "") or ""
            project = project or getattr(obj, "project", None)
            organization = organization or getattr(obj, "organization", None) or (
                getattr(project, "organization", None) if project else None
            )

        entry = AuditLog.objects.create(
            organization=organization,
            project=project,
            user=user or (getattr(request, "user", None) if request and request.user.is_authenticated else None),
            action=action,
            object_type=str(object_type),
            object_id=object_id,
            object_ref=str(object_ref or ""),
            old_data=old_data,
            new_data=new_data,
            ip_address=client_ip(request) if request else None,
            user_agent=user_agent(request) if request else "",
            request_id=getattr(request, "request_id", "") if request else "",
        )
        logger.info("audit %s %s#%s", action, object_type, object_id)
        return entry
