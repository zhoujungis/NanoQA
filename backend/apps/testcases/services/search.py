"""用例搜索（§31）：q 高级搜索解析 + 列表筛选参数。

q 语法：`priority:P0 status:active module:login tag:smoke automation:automated`，
token 之间 AND；非法 token（未知 key / 非法值 / 空值）退化为普通文本，
按 case_key/title/description/precondition/当前版本 expected_result icontains。
"""
from dataclasses import dataclass, field

from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.projects.models import Module
from apps.testcases.models import TestCase, TestCaseVersion
from common.exceptions import NanoAPIError

PRIORITY_VALUES = {"p0": "P0", "p1": "P1", "p2": "P2", "p3": "P3"}
STATUS_VALUES = {"draft", "active", "deprecated", "archived"}
AUTOMATION_VALUES = {"manual", "automated", "partial", "not_automatable"}
CASE_TYPE_VALUES = {choice[0] for choice in TestCase.TYPE_CHOICES}

TEXT_FIELDS = ["case_key", "title", "description", "precondition"]

ORDERING_MAP = {
    "updated_at": "updated_at",
    "-updated_at": "-updated_at",
    "priority": "priority",
    "-priority": "-priority",
    "case_key": "case_key",
    "-case_key": "-case_key",
}
DEFAULT_ORDERING = "-updated_at"


@dataclass
class SearchQuery:
    priority: list[str] = field(default_factory=list)
    status: list[str] = field(default_factory=list)
    automation: list[str] = field(default_factory=list)
    module: list[str] = field(default_factory=list)
    tag: list[str] = field(default_factory=list)
    text: list[str] = field(default_factory=list)


def parse_q(q: str) -> SearchQuery:
    """解析 q 高级搜索语法；非法 token 当普通文本。"""
    result = SearchQuery()
    if not q:
        return result
    for raw in q.split():
        key, sep, value = raw.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if not sep or not value:
            result.text.append(raw)
            continue
        if key == "priority" and value.lower() in PRIORITY_VALUES:
            result.priority.append(PRIORITY_VALUES[value.lower()])
        elif key == "status" and value.lower() in STATUS_VALUES:
            result.status.append(value.lower())
        elif key == "automation" and value.lower() in AUTOMATION_VALUES:
            result.automation.append(value.lower())
        elif key == "module":
            result.module.append(value)
        elif key == "tag":
            result.tag.append(value)
        else:
            result.text.append(raw)
    return result


def _text_q(term: str) -> Q:
    matched = TestCaseVersion.objects.filter(
        test_case=OuterRef("pk"),
        version=OuterRef("current_version"),
        expected_result__icontains=term,
    ).values("test_case_id")
    q = Q(pk__in=Subquery(matched))
    for name in TEXT_FIELDS:
        q |= Q(**{f"{name}__icontains": term})
    return q


def apply_search(queryset, search: SearchQuery):
    """把解析结果叠加到 queryset（token 之间 AND）。"""
    for value in search.priority:
        queryset = queryset.filter(priority=value)
    for value in search.status:
        queryset = queryset.filter(status=value)
    for value in search.automation:
        queryset = queryset.filter(automation_status=value)
    for value in search.module:
        queryset = queryset.filter(module__name__icontains=value)
    for value in search.tag:
        queryset = queryset.filter(tags__name__icontains=value)
    for term in search.text:
        queryset = queryset.filter(_text_q(term))
    return queryset.distinct()


def collect_module_ids(project, module_id: int, include_descendants: bool) -> list[int]:
    if not Module.objects.filter(pk=module_id, project=project).exists():
        raise NanoAPIError("模块不存在或不属于当前项目")
    ids = [module_id]
    if include_descendants:
        frontier = [module_id]
        while frontier:
            children = list(
                Module.objects.filter(project=project, parent_id__in=frontier).values_list("id", flat=True)
            )
            new_ids = [child_id for child_id in children if child_id not in ids]
            ids.extend(new_ids)
            frontier = new_ids
    return ids


def _enum_param(params, name: str, allowed: set[str], upper: bool = False):
    raw = params.get(name)
    if raw in (None, ""):
        return None
    value = str(raw).lower()
    if value not in allowed:
        raise NanoAPIError(f"{name} 参数非法: {raw}")
    return value.upper() if upper else value


def _int_param(params, name: str):
    raw = params.get(name)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise NanoAPIError(f"{name} 参数非法: {raw}")


def _datetime_param(params, name: str):
    raw = params.get(name)
    if raw in (None, ""):
        return None
    parsed = parse_datetime(str(raw))
    if parsed is None:
        raise NanoAPIError(f"{name} 参数非法: {raw}")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def build_case_queryset(project, params):
    """列表/搜索 queryset：q + 全部筛选参数 + 排序。"""
    queryset = (
        TestCase.objects.filter(project=project)
        .select_related("module", "owner", "creator")
        .prefetch_related("tags")
    )
    queryset = apply_search(queryset, parse_q(params.get("q") or ""))

    module_id = _int_param(params, "module_id")
    if module_id is not None:
        include = str(params.get("include_submodules", "")).lower() in {"1", "true", "yes"}
        queryset = queryset.filter(module_id__in=collect_module_ids(project, module_id, include))

    priority = _enum_param(params, "priority", set(PRIORITY_VALUES), upper=True)
    if priority:
        queryset = queryset.filter(priority=priority)
    case_type = _enum_param(params, "case_type", CASE_TYPE_VALUES)
    if case_type:
        queryset = queryset.filter(case_type=case_type)
    status_value = _enum_param(params, "status", STATUS_VALUES)
    if status_value:
        queryset = queryset.filter(status=status_value)
    automation = _enum_param(params, "automation_status", AUTOMATION_VALUES)
    if automation:
        queryset = queryset.filter(automation_status=automation)

    owner_id = _int_param(params, "owner_id")
    if owner_id is not None:
        queryset = queryset.filter(owner_id=owner_id)

    tag = params.get("tag")
    if tag:
        queryset = queryset.filter(tags__name__icontains=tag)

    created_start = _datetime_param(params, "created_at_start")
    if created_start:
        queryset = queryset.filter(created_at__gte=created_start)
    created_end = _datetime_param(params, "created_at_end")
    if created_end:
        queryset = queryset.filter(created_at__lte=created_end)
    updated_start = _datetime_param(params, "updated_at_start")
    if updated_start:
        queryset = queryset.filter(updated_at__gte=updated_start)
    updated_end = _datetime_param(params, "updated_at_end")
    if updated_end:
        queryset = queryset.filter(updated_at__lte=updated_end)

    return apply_ordering(queryset, params.get("ordering"))


def apply_ordering(queryset, ordering):
    key = ordering or DEFAULT_ORDERING
    field_name = ORDERING_MAP.get(key)
    if field_name is None:
        raise NanoAPIError(f"ordering 参数非法: {ordering}")
    return queryset.order_by(field_name)
