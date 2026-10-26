"""公共工具：对象 diff、编号格式化、请求元信息。"""
from django.db import models


def model_diff(old: dict, new: dict) -> tuple[dict, dict]:
    """返回 (old_data, new_data)，只包含发生变化的字段。"""
    old_data, new_data = {}, {}
    for key, new_value in new.items():
        old_value = old.get(key)
        if old_value != new_value:
            old_data[key] = _plain(old_value)
            new_data[key] = _plain(new_value)
    return old_data, new_data


def model_snapshot(instance, fields: list[str] | None = None) -> dict:
    data = {}
    for field in instance._meta.concrete_fields:
        if fields and field.name not in fields:
            continue
        data[field.name] = _plain(getattr(instance, field.name))
    return data


def _plain(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, models.Model):
        return value.pk
    return value


def format_key(project_key: str, entity: str, number: int, width: int = 6) -> str:
    """编号格式：SHOP-TC-000001（§49）。"""
    return f"{project_key}-{entity}-{number:0{width}d}"


def client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def user_agent(request) -> str:
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT") or ""
