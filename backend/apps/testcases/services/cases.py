"""测试用例业务：创建 + 版本化 + 乐观锁 + 软删 + 编号（§49-§52）。

多表写入必须与审计同事务（§51）。
"""
from django.db import transaction
from django.db.models import prefetch_related_objects

from apps.audit.services import AuditService
from apps.projects.models import Module, Tag
from apps.projects.services.keys import next_key
from apps.testcases.models import TestCase, TestCaseTag
from apps.testcases.services.versions import create_version, get_current_version
from common.exceptions import NanoAPIError
from common.optimistic import save_with_lock
from common.statemachine import validate_transition
from common.utils import model_diff, model_snapshot

# 参与审计 diff 的用例字段（不含时间戳噪声）
DIFF_FIELDS = [
    "title", "description", "precondition", "priority", "case_type", "status",
    "automation_status", "automation_framework", "automation_identifier",
    "automation_script", "module", "owner", "current_version",
]

DEFAULT_CHANGE_SUMMARY = "更新内容"


def resolve_module(project, module_id):
    if module_id is None:
        return None
    module = Module.objects.filter(pk=module_id, project=project).first()
    if module is None:
        raise NanoAPIError("模块不存在或不属于当前项目")
    return module


def resolve_owner(owner_id):
    if owner_id is None:
        return None
    from apps.accounts.models import User

    try:
        return User.objects.get(pk=owner_id)
    except User.DoesNotExist:
        raise NanoAPIError("负责人不存在")


def resolve_tags(project, tag_ids) -> list[Tag]:
    tags = []
    for tag_id in dict.fromkeys(tag_ids or []):
        tag = Tag.objects.filter(pk=tag_id, project=project).first()
        if tag is None:
            raise NanoAPIError(f"标签不存在或不属于当前项目: {tag_id}")
        tags.append(tag)
    return tags


def set_tags(case, tag_ids):
    tags = resolve_tags(case.project, tag_ids)
    TestCaseTag.objects.filter(test_case=case).exclude(tag__in=tags).delete()
    existing = set(TestCaseTag.objects.filter(test_case=case).values_list("tag_id", flat=True))
    TestCaseTag.objects.bulk_create(
        [TestCaseTag(test_case=case, tag=tag) for tag in tags if tag.id not in existing]
    )
    # 复用实例上可能已带失效的 prefetch 缓存（prefetch_related_objects 会跳过已缓存实例），
    # 先清掉再刷新，保证后续序列化读到最新 tags
    cache = getattr(case, "_prefetched_objects_cache", None)
    if cache is not None:
        cache.pop("tags", None)
    prefetch_related_objects([case], "tags")


def _audit_snapshot(case, tag_ids, steps, expected_result) -> dict:
    data = model_snapshot(case, fields=DIFF_FIELDS)
    data["tag_ids"] = sorted(tag_ids)
    data["steps"] = steps
    data["expected_result"] = expected_result
    return data


def create_case(project, data: dict, user, request=None) -> TestCase:
    """创建用例：编号 + 用例 + v1 版本 + 审计 同事务。"""
    with transaction.atomic():
        case = TestCase.objects.create(
            organization=project.organization,
            project=project,
            module=resolve_module(project, data.get("module_id")),
            case_key=next_key(project, "TC"),
            title=data["title"],
            description=data.get("description") or "",
            precondition=data.get("precondition") or "",
            priority=data["priority"],
            case_type=data.get("case_type") or "functional",
            status=data.get("status") or TestCase.STATUS_DRAFT,
            creator=user,
            owner=resolve_owner(data.get("owner_id")),
            current_version=1,
        )
        create_version(
            case,
            version=1,
            title=case.title,
            description=case.description,
            precondition=case.precondition,
            steps=data["steps"],
            expected_result=data.get("expected_result") or "",
            change_summary="初始版本",
            created_by=user,
        )
        set_tags(case, data.get("tag_ids"))
        AuditService.record(
            "create", case, request=request, user=user,
            new_data=_audit_snapshot(case, [tag.id for tag in case.tags.all()], data["steps"], data.get("expected_result") or ""),
        )
    return case


def update_case(case, data: dict, user, request=None):
    """乐观锁更新；内容变化 → 新版本并推进 current_version。"""
    with transaction.atomic():
        version = get_current_version(case)
        old_tag_ids = list(case.tags.values_list("id", flat=True))

        new_title = data.get("title", case.title)
        new_precondition = data.get("precondition", case.precondition)
        new_description = data.get("description", case.description)
        new_steps = data.get("steps", version.steps)
        new_expected = data.get("expected_result", version.expected_result)
        new_status = data.get("status", case.status)

        if new_status != case.status:
            validate_transition("testcase", case.status, new_status)

        content_changed = (
            new_title != case.title
            or new_precondition != case.precondition
            or new_description != case.description
            or new_steps != version.steps
            or new_expected != version.expected_result
        )

        old_snapshot = _audit_snapshot(case, old_tag_ids, version.steps, version.expected_result)

        case.title = new_title
        case.precondition = new_precondition
        case.description = new_description
        case.status = new_status
        for attr in (
            "priority", "case_type", "automation_status", "automation_framework",
            "automation_identifier", "automation_script",
        ):
            if attr in data:
                setattr(case, attr, data[attr])
        if "module_id" in data:
            case.module = resolve_module(case.project, data["module_id"])
        if "owner_id" in data:
            case.owner = resolve_owner(data["owner_id"])

        current = version
        if content_changed:
            current = create_version(
                case,
                version=case.current_version + 1,
                title=new_title,
                description=new_description,
                precondition=new_precondition,
                steps=new_steps,
                expected_result=new_expected,
                change_summary=data.get("change_summary") or DEFAULT_CHANGE_SUMMARY,
                created_by=user,
            )
            case.current_version = current.version

        save_with_lock(
            case,
            data.get("updated_at"),
            ["title", "precondition", "description", "status", "priority", "case_type",
             "automation_status", "automation_framework", "automation_identifier",
             "automation_script", "module", "owner", "current_version"],
        )

        if "tag_ids" in data:
            set_tags(case, data["tag_ids"])

        new_snapshot = _audit_snapshot(
            case, [tag.id for tag in case.tags.all()], new_steps, new_expected
        )
        old_diff, new_diff = model_diff(old_snapshot, new_snapshot)
        AuditService.record(
            "update", case, request=request, user=user,
            old_data=old_diff or None, new_data=new_diff or None,
        )
    return case, current


def delete_case(case, user, request=None):
    """软删：测试数据是质量资产，不做物理删除（坑 5）。"""
    with transaction.atomic():
        snapshot = _audit_snapshot(
            case, list(case.tags.values_list("id", flat=True)),
            None, None,
        )
        case.soft_delete()
        AuditService.record("delete", case, request=request, user=user, old_data=snapshot)
    return case


def restore_case(case, user, request=None):
    with transaction.atomic():
        old_data = {"deleted_at": case.deleted_at.isoformat() if case.deleted_at else None}
        case.restore()
        AuditService.record("update", case, request=request, user=user, old_data=old_data, new_data={"deleted_at": None})
    return case


def duplicate_case(case, user, request=None) -> TestCase:
    """复制为新用例：新编号 + 标题加「副本」+ 当前版本复制为 v1 + 复制标签。"""
    with transaction.atomic():
        source = get_current_version(case)
        new_case = TestCase.objects.create(
            organization=case.organization,
            project=case.project,
            module=case.module,
            case_key=next_key(case.project, "TC"),
            title=f"{case.title}副本"[:255],
            description=case.description,
            precondition=case.precondition,
            priority=case.priority,
            case_type=case.case_type,
            automation_status=case.automation_status,
            automation_framework=case.automation_framework,
            automation_identifier=case.automation_identifier,
            automation_script=case.automation_script,
            status=case.status,
            creator=user,
            owner=case.owner,
            current_version=1,
        )
        create_version(
            new_case,
            version=1,
            title=new_case.title,
            description=source.description,
            precondition=source.precondition,
            steps=source.steps,
            expected_result=source.expected_result,
            change_summary=f"复制自 {case.case_key}",
            created_by=user,
        )
        set_tags(new_case, list(case.tags.values_list("id", flat=True)))
        AuditService.record(
            "create", new_case, request=request, user=user,
            new_data=_audit_snapshot(new_case, [tag.id for tag in new_case.tags.all()], source.steps, source.expected_result),
        )
    return new_case


def move_case(case, module_id, user, request=None) -> TestCase:
    """移动到目标模块。"""
    with transaction.atomic():
        module = resolve_module(case.project, module_id)
        old_data = {"module": case.module_id, "module_name": case.module.name if case.module else None}
        case.module = module
        case.save(update_fields=["module", "updated_at"])
        AuditService.record(
            "update", case, request=request, user=user,
            old_data=old_data,
            new_data={"module": module.id if module else None, "module_name": module.name if module else None},
        )
    return case
