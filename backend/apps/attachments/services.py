"""附件服务（§53）：mime/size 校验 → 存储 → 元数据 → 审计。"""
from django.conf import settings
from django.db import transaction

from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.attachments.models import Attachment
from apps.defects.models import Defect
from apps.executions.models import TestResult, TestRun
from apps.requirements.models import Requirement
from apps.testcases.models import TestCase
from common.exceptions import CODE_VALIDATION_ERROR, NanoAPIError, NotFoundError
from common.storage import get_storage

OBJECT_MODELS = {
    "testcase": TestCase,
    "requirement": Requirement,
    "defect": Defect,
    "testrun": TestRun,
    "testresult": TestResult,
}

# 对象类型 → 写权限码（上传/删除），读权限码（下载）
OBJECT_UPDATE_PERMISSION = {
    "testcase": "testcase.update",
    "requirement": "requirement.update",
    "defect": "defect.update",
    "testrun": "testcase.execute",
    "testresult": "testcase.execute",
}
OBJECT_READ_PERMISSION = {
    "testcase": "testcase.read",
    "requirement": "requirement.read",
    "defect": "defect.read",
    "testrun": "testcase.read",
    "testresult": "testcase.read",
}


def resolve_target(object_type: str, object_id: int, project):
    """附件对象必须存在且归属同一项目（对象即权限边界，§70）。"""
    if object_type not in OBJECT_MODELS:
        raise NanoAPIError("不支持的附件对象类型")
    target = OBJECT_MODELS[object_type].objects.filter(pk=object_id).first()
    if target is None:
        raise NotFoundError("附件对象不存在")
    target_project_id = getattr(target, "project_id", None) or target.test_run.project_id
    if target_project_id != project.id:
        raise NanoAPIError("附件对象与项目不匹配")
    return target


@transaction.atomic
def create_attachment(*, file, object_type: str, object_id: int, project, user, request=None) -> Attachment:
    resolve_target(object_type, object_id, project)

    mime_type = getattr(file, "content_type", "") or "application/octet-stream"
    if mime_type not in settings.ATTACHMENT_ALLOWED_MIME:
        raise NanoAPIError(f"不支持的文件类型: {mime_type}", code=CODE_VALIDATION_ERROR)
    if file.size > settings.ATTACHMENT_MAX_SIZE:
        raise NanoAPIError(
            f"文件大小超过限制（最大 {settings.ATTACHMENT_MAX_SIZE} 字节）", code=CODE_VALIDATION_ERROR
        )

    storage_key = get_storage().save(file, file.name)
    attachment = Attachment.objects.create(
        organization=project.organization,
        project=project,
        object_type=object_type,
        object_id=object_id,
        filename=file.name,
        storage_key=storage_key,
        mime_type=mime_type,
        size=file.size,
        uploaded_by=user,
    )
    AuditService.record(
        AuditLog.ACTION_CREATE, attachment, request=request, user=user,
        new_data={"filename": attachment.filename, "size": attachment.size, "object_type": object_type},
    )
    return attachment


@transaction.atomic
def delete_attachment(attachment: Attachment, request=None) -> None:
    AuditService.record(
        AuditLog.ACTION_DELETE, attachment, request=request,
        object_ref=attachment.filename,
        old_data={"filename": attachment.filename, "storage_key": attachment.storage_key},
    )
    get_storage().delete(attachment.storage_key)
    attachment.delete()
