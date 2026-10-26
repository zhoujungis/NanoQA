"""乐观锁（§52）：客户端回传 updated_at 原值，不匹配 → 409 + code 40003。"""
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from common.exceptions import OptimisticLockError


def parse_updated_at(value):
    """解析客户端回传的 updated_at（ISO 微秒字符串原样回传，禁止前端格式化）。"""
    if value in (None, ""):
        raise OptimisticLockError("缺少 updated_at（乐观锁版本字段）")
    if isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed is None:
            raise OptimisticLockError("updated_at 格式非法")
        return parsed
    return value


def save_with_lock(obj, expected_updated_at, update_fields: list[str]):
    """带乐观锁的更新：WHERE id=%s AND updated_at=%s，0 行 → 冲突。"""
    expected = parse_updated_at(expected_updated_at)
    new_updated_at = timezone.now()
    values = {field: getattr(obj, field) for field in update_fields}
    values["updated_at"] = new_updated_at

    rows = type(obj).objects.filter(pk=obj.pk, updated_at=expected).update(**values)
    if rows == 0:
        exists = type(obj).all_objects.filter(pk=obj.pk).exists() if hasattr(type(obj), "all_objects") else type(obj).objects.filter(pk=obj.pk).exists()
        if not exists:
            from common.exceptions import NotFoundError
            raise NotFoundError("资源不存在")
        raise OptimisticLockError("该记录已被其他用户修改，请刷新后重新编辑")
    obj.updated_at = new_updated_at
    return obj
