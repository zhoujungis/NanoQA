"""导入 / 导出服务（§61）：CSV / XLSX 解析、字段映射、逐行校验、批量入库、导出。

导入流程严格按 §61：上传 → 字段映射 → 数据预览 → 错误检查 → 确认导入，
预览（dry_run=True）只解析校验不落库；确认（dry_run=False）复用同一套校验，
合法行批量入库（用例 + 版本 1 快照 + 编号递增），非法行跳过并逐行回报。
"""
import csv
import io
import re
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from apps.accounts.models import User
from apps.projects.models import Module, Tag
from apps.testcases.models import TestCase, TestCaseVersion
from apps.testcases.services import cases as cases_service
from apps.testcases.services import search as search_service
from common.exceptions import NanoAPIError
from common.statemachine import validate_transition

MAX_FILE_SIZE = 10 * 1024 * 1024  # 与前端一致：10MB
ALLOWED_EXTENSIONS = {"csv", "xlsx"}

# ---------------------------------------------------------------- 导出定义
# 列顺序即表头顺序；步骤导出为可读文本，回导时可被 parse_steps 解析
EXPORT_COLUMNS = [
    ("case_key", "用例编号"),
    ("title", "标题"),
    ("module_path", "模块路径"),
    ("priority", "优先级"),
    ("case_type", "类型"),
    ("status", "状态"),
    ("precondition", "前置条件"),
    ("steps", "步骤"),
    ("expected_result", "预期结果"),
    ("tags", "标签"),
    ("owner", "负责人"),
]

# 列宽（Excel 可读性）
COLUMN_WIDTHS = {
    "用例编号": 18, "标题": 40, "模块路径": 28, "优先级": 8, "类型": 10, "状态": 8,
    "前置条件": 30, "步骤": 60, "预期结果": 30, "标签": 22, "负责人": 12,
}

TYPE_LABELS = dict(TestCase.TYPE_CHOICES)
STATUS_LABELS = dict(TestCase.STATUS_CHOICES)

# ---------------------------------------------------------------- 导入定义
# 系统字段 → 中文名（预览表与映射 UI 使用）
FIELD_LABELS = {
    "title": "标题",
    "module": "模块路径",
    "priority": "优先级",
    "case_type": "类型",
    "status": "状态",
    "precondition": "前置条件",
    "steps": "步骤",
    "expected_result": "预期结果",
    "tags": "标签",
    "owner": "负责人",
    "case_key": "用例编号",
    "description": "描述",
}

# 系统字段 → 常见表头别名（中英文，自动猜测用）
HEADER_ALIASES = {
    "title": ["标题", "用例标题", "用例名称", "名称", "title", "case title", "name", "test case"],
    "module": ["模块", "模块路径", "所属模块", "module", "module path", "directory"],
    "priority": ["优先级", "priority", "p"],
    "case_type": ["类型", "用例类型", "case type", "type", "case_type"],
    "status": ["状态", "status", "case status"],
    "precondition": ["前置条件", "前提条件", "预置条件", "precondition", "prerequisite", "pre-condition"],
    "steps": ["步骤", "测试步骤", "操作步骤", "steps", "step", "test steps", "action"],
    "expected_result": ["预期结果", "期望结果", "预期", "expected", "expected result", "expected_result"],
    "tags": ["标签", "tag", "tags", "labels"],
    "owner": ["负责人", "处理人", "owner", "assignee"],
    "case_key": ["用例编号", "编号", "case key", "case_key", "key", "id"],
    "description": ["描述", "说明", "description", "desc"],
}

# 优先级：空值默认 P1；兼容小写与中文别名
PRIORITY_ALIASES = {"p0": "P0", "p1": "P1", "p2": "P2", "p3": "P3", "0": "P0", "1": "P1", "2": "P2", "3": "P3"}
TYPE_ALIASES = {value: value for value in TYPE_LABELS}
TYPE_ALIASES.update({label: value for value, label in TestCase.TYPE_CHOICES})
STATUS_ALIASES = {value: value for value in STATUS_LABELS}
STATUS_ALIASES.update({label: value for value, label in TestCase.STATUS_CHOICES})

# 步骤行分隔符：1. 操作 → 预期
STEP_SEPARATOR = re.compile(r"\s*(?:→|->|=>)\s*")
STEP_NUMBERING = re.compile(r"^\s*(?:\d+|[一二三四五六七八九十]+)\s*[.、)）:：]\s*")
MODULE_SEPARATORS = re.compile(r"[/\\>＞／]+")
TAG_SEPARATORS = re.compile(r"[,，、;；]+")


# ================================================================ 导出
def _module_path_text(module) -> str:
    chain = []
    cursor = module
    while cursor is not None:
        chain.append(cursor.name)
        cursor = cursor.parent
    chain.reverse()
    return "/".join(chain)


def _steps_text(steps: list) -> str:
    """步骤导出为可读文本：`1. 操作 → 预期`。"""
    lines = []
    for index, step in enumerate(steps or [], 1):
        if not isinstance(step, dict):
            continue
        lines.append(f"{index}. {step.get('action', '')} → {step.get('expected', '')}")
    return "\n".join(lines)


def build_export_rows(queryset) -> list[list[str]]:
    """组装导出行；当前版本内容用 Subquery 一次性取，避免 N+1。"""
    current = TestCaseVersion.objects.filter(
        test_case=OuterRef("pk"), version=OuterRef("current_version")
    )
    queryset = queryset.annotate(
        cv_steps=Subquery(current.values("steps")[:1]),
        cv_expected=Subquery(current.values("expected_result")[:1]),
    )
    rows = []
    for case in queryset:
        rows.append([
            case.case_key,
            case.title,
            _module_path_text(case.module) if case.module_id else "",
            case.priority,
            TYPE_LABELS.get(case.case_type, case.case_type),
            STATUS_LABELS.get(case.status, case.status),
            case.precondition or "",
            _steps_text(case.cv_steps or []),
            case.cv_expected or "",
            ", ".join(tag.name for tag in case.tags.all()),
            (case.owner.display_name or case.owner.username) if case.owner_id else "",
        ])
    return rows


def render_csv(headers: list[str], rows: list[list[str]]) -> bytes:
    """CSV 用 UTF-8-BOM，Excel 打开中文不乱码。"""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def render_xlsx(headers: list[str], rows: list[list[str]]) -> bytes:
    """XLSX：表头加粗 + 冻结首行 + 合理列宽 + 步骤列自动换行。"""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "测试用例"
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(vertical="center")
    for row in rows:
        sheet.append(row)
    for index, name in enumerate(headers, 1):
        sheet.column_dimensions[get_column_letter(index)].width = COLUMN_WIDTHS.get(name, 16)
    steps_index = headers.index("步骤") + 1 if "步骤" in headers else None
    if steps_index:
        for row_cells in sheet.iter_rows(min_row=2, min_col=steps_index, max_col=steps_index):
            for cell in row_cells:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
    sheet.freeze_panes = "A2"

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def export_cases(project, params, fmt: str):
    """按列表口径（module_id/status/priority 等）导出当前项目用例。

    返回 (文件名, content_type, 文件字节)；调用方负责 Content-Disposition。
    """
    fmt = (fmt or "").lower()
    if fmt not in {"csv", "xlsx"}:
        raise NanoAPIError("format 参数仅支持 csv 或 xlsx")
    queryset = search_service.build_case_queryset(project, params)
    headers = [title for _field, title in EXPORT_COLUMNS]
    rows = build_export_rows(queryset)

    stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    filename = f"{project.key}_testcases_{stamp}.{fmt}"
    if fmt == "csv":
        return filename, "text/csv; charset=utf-8", render_csv(headers, rows)
    return (
        filename,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        render_xlsx(headers, rows),
    )


# ================================================================ 导入：解析
def _cell_text(value) -> str:
    """单元格统一转文本：数字去掉浮点尾巴，None 转空串。"""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_file(file_name: str, content: bytes):
    """解析 CSV / XLSX → (表头列表, 数据行列表[dict(header→文本)])。

    解析失败抛 NanoAPIError（业务码 40006）。
    """
    if not file_name or "." not in file_name:
        raise NanoAPIError("文件名非法，仅支持 CSV 或 XLSX 格式")
    extension = file_name.rsplit(".", 1)[-1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise NanoAPIError("仅支持 CSV 或 XLSX 格式的文件")
    if not content:
        raise NanoAPIError("文件内容为空")
    if len(content) > MAX_FILE_SIZE:
        raise NanoAPIError("文件大小不能超过 10MB")

    if extension == "csv":
        matrix = _parse_csv(content)
    else:
        matrix = _parse_xlsx(content)

    headers, data_rows = _split_matrix(matrix, file_name)
    return headers, data_rows


def _parse_csv(content: bytes) -> list[list[str]]:
    text = None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise NanoAPIError("CSV 文件编码无法识别，请另存为 UTF-8 后重试")
    try:
        return [[_cell_text(cell) for cell in row] for row in csv.reader(io.StringIO(text))]
    except csv.Error as exc:
        raise NanoAPIError(f"CSV 解析失败：{exc}")


def _parse_xlsx(content: bytes) -> list[list[str]]:
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - openpyxl 异常类型不固定，统一转业务错误
        raise NanoAPIError(f"XLSX 文件解析失败，请确认文件未损坏：{exc}")
    try:
        sheet = workbook.active
        return [[_cell_text(cell) for cell in row] for row in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()


def _split_matrix(matrix: list[list[str]], file_name: str):
    """第一行非空行为表头；表头前的空行忽略，行内全空的行保留（导入时按空行跳过）。"""
    start = None
    for index, row in enumerate(matrix):
        if any(cell for cell in row):
            start = index
            break
    if start is None:
        raise NanoAPIError(f"文件「{file_name}」没有可导入的数据")
    headers = [cell for cell in matrix[start]]
    if not any(headers):
        raise NanoAPIError(f"文件「{file_name}」缺少表头行")
    data_rows = matrix[start + 1:]
    return headers, data_rows


def _normalize_header(header: str) -> str:
    """表头归一：去空白/下划线/连字符后小写，兼容 Case Key / case_key 等写法。"""
    return re.sub(r"[\s_\-（）()]+", "", (header or "").lower())


def guess_mapping(headers: list[str]) -> dict[str, str]:
    """按中英文常见表头自动猜测字段映射：{系统字段: 文件表头}。"""
    mapping: dict[str, str] = {}
    normalized = {}
    for header in headers:
        key = _normalize_header(header)
        if key and key not in normalized:
            normalized[key] = header
    for field_name, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            header = normalized.get(_normalize_header(alias))
            if header is not None and header not in mapping.values():
                mapping[field_name] = header
                break
    return mapping


# ================================================================ 导入：行校验
@dataclass
class RowResult:
    """一行的解析结果：action ∈ create / update / skip。"""

    line: int
    action: str
    errors: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    # 确认阶段使用的定位信息（不外泄给前端）
    case_id: int | None = None
    # 单元格是否有值：更新时只覆盖有值字段，空单元格保留原值
    provided: dict = field(default_factory=dict)


def parse_steps(text: str, fallback_expected: str = "") -> tuple[list[dict], list[str]]:
    """解析步骤文本：`1. 操作 → 预期` 多行；无分隔符时预期结果回退 expected_result 列。

    返回 (steps, errors)；steps 与 normalize_steps 结构一致 [{order,action,expected}]。
    """
    steps, errors = [], []
    lines = [line.strip() for line in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    fallback = (fallback_expected or "").strip()
    order = 0
    for raw in lines:
        if not raw:
            continue
        line = STEP_NUMBERING.sub("", raw)
        parts = STEP_SEPARATOR.split(line, maxsplit=1)
        action = parts[0].strip()
        expected = parts[1].strip() if len(parts) > 1 else fallback
        order += 1
        if not action:
            errors.append(f"步骤 {order} 缺少操作描述")
            continue
        if not expected:
            errors.append(f"步骤 {order} 缺少预期结果（可用「→」分隔操作与预期）")
            continue
        steps.append({"order": order, "action": action, "expected": expected})
    if not steps and not errors:
        errors.append("步骤不能为空")
    return steps, errors


def _normalize_enum(value: str, aliases: dict[str, str], label: str) -> tuple[str | None, str | None]:
    """枚举归一：返回 (取值, 错误)。空值返回 ("", None) 由调用方给默认值。"""
    text = (value or "").strip()
    if not text:
        return "", None
    normalized = aliases.get(text) or aliases.get(text.lower()) or aliases.get(text.upper())
    if normalized is None:
        allowed = "、".join(dict.fromkeys(aliases.values()))
        return None, f"{label}取值非法：{value}（可选 {allowed}）"
    return normalized, None


def _resolve_owner(text: str, cache: dict) -> tuple[User | None, str | None]:
    """负责人按 显示名 / 用户名 / 邮箱 / 用户 ID 精确匹配；找不到返回错误。"""
    key = (text or "").strip()
    if not key:
        return None, None
    if key in cache:
        return cache[key], None
    user = None
    if key.isdigit():
        user = User.objects.filter(pk=int(key)).first()
    if user is None:
        user = (
            User.objects.filter(display_name=key).first()
            or User.objects.filter(username=key).first()
            or User.objects.filter(email__iexact=key).first()
        )
    if user is None:
        return None, f"负责人不存在：{key}"
    cache[key] = user
    return user, None


def _split_tags(text: str) -> list[str]:
    names = []
    for part in TAG_SEPARATORS.split(text or ""):
        name = part.strip()
        if name and name not in names:
            names.append(name)
    return names


def _split_module_path(text: str) -> list[str]:
    return [part.strip() for part in MODULE_SEPARATORS.split(text or "") if part.strip()]


class ImportContext:
    """跨行复用的查找缓存（用例编号/标题/负责人），避免逐行查库。"""

    def __init__(self, project):
        self.project = project
        self.by_key: dict[str, dict] = {}
        self.by_title: dict[str, dict] = {}
        for row in TestCase.objects.filter(project=project).values(
            "id", "case_key", "title", "status", "updated_at"
        ):
            self.by_key[row["case_key"]] = row
            self.by_title.setdefault(row["title"], row)
        self.owner_cache: dict[str, User] = {}
        self.seen_keys: dict[str, int] = {}
        self.seen_titles: dict[str, int] = {}


def _row_values(headers: list[str], raw: list, mapping: dict[str, str]) -> dict[str, str]:
    index_by_header = {header: index for index, header in enumerate(headers)}
    values = {}
    for field_name, header in mapping.items():
        index = index_by_header.get(header)
        values[field_name] = _cell_text(raw[index]) if index is not None and index < len(raw) else ""
    return values


def validate_row(project, line: int, headers: list[str], raw: list, mapping: dict, ctx: ImportContext) -> RowResult:
    """逐行校验：标题必填、枚举合法、步骤解析、用例编号定位动作（create/update/skip）。"""
    values = _row_values(headers, raw, mapping)
    result = RowResult(line=line, action="create", data={})
    result.provided = {key: bool(value.strip()) for key, value in values.items()}

    if not any(str(cell or "").strip() for cell in raw):
        result.action = "skip"
        result.errors.append(f"第 {line} 行：空行，已跳过")
        return result

    # 标题必填
    title = values.get("title", "").strip()
    if "title" not in mapping:
        result.errors.append(f"第 {line} 行：未映射「标题」列，无法导入")
    elif not title:
        result.errors.append(f"第 {line} 行：标题不能为空")
    elif len(title) > 255:
        result.errors.append(f"第 {line} 行：标题长度不能超过 255 个字符")

    # 枚举字段
    priority, error = _normalize_enum(values.get("priority", ""), PRIORITY_ALIASES, "优先级")
    if error:
        result.errors.append(f"第 {line} 行：{error}")
        priority = "P1"
    priority = priority or "P1"
    case_type, error = _normalize_enum(values.get("case_type", ""), TYPE_ALIASES, "类型")
    if error:
        result.errors.append(f"第 {line} 行：{error}")
        case_type = "functional"
    case_type = case_type or "functional"
    status, error = _normalize_enum(values.get("status", ""), STATUS_ALIASES, "状态")
    if error:
        result.errors.append(f"第 {line} 行：{error}")
        status = "draft"
    status = status or "draft"

    # 步骤解析
    steps, step_errors = parse_steps(values.get("steps", ""), values.get("expected_result", ""))
    for message in step_errors:
        result.errors.append(f"第 {line} 行：{message}")

    # 负责人
    owner, error = _resolve_owner(values.get("owner", ""), ctx.owner_cache)
    if error:
        result.errors.append(f"第 {line} 行：{error}")

    # 标签
    tags = _split_tags(values.get("tags", ""))
    for name in tags:
        if len(name) > 64:
            result.errors.append(f"第 {line} 行：标签名称过长（最多 64 字符）：{name}")

    # 动作定位：编号 → 标题
    case_key = values.get("case_key", "").strip()
    matched = None
    if case_key:
        matched = ctx.by_key.get(case_key)
        if matched is None:
            result.errors.append(f"第 {line} 行：用例编号不存在：{case_key}")
    elif title:
        matched = ctx.by_title.get(title)

    if matched is not None:
        result.action = "update"
        result.case_id = matched["id"]
        # 更新行校验状态机流转，避免确认阶段才报错
        new_status = status if result.provided.get("status") else matched["status"]
        if new_status != matched["status"]:
            try:
                validate_transition("testcase", matched["status"], new_status)
            except Exception as exc:  # noqa: BLE001 - 状态机异常文案已中文化
                result.errors.append(f"第 {line} 行：{exc}")

    # 文件内重复行：同编号或同标题 → 跳过
    if result.action != "skip":
        seen_line = ctx.seen_keys.get(case_key) if case_key else None
        if seen_line is None and title:
            seen_line = ctx.seen_titles.get(title)
        if seen_line is not None:
            result.action = "skip"
            result.errors.append(f"第 {line} 行：与第 {seen_line} 行内容重复，已跳过")
        else:
            if case_key:
                ctx.seen_keys[case_key] = line
            if title:
                ctx.seen_titles.setdefault(title, line)

    result.data = {
        "case_key": case_key,
        "title": title,
        "module": "/".join(_split_module_path(values.get("module", ""))),
        "priority": priority,
        "case_type": case_type,
        "status": status,
        "precondition": values.get("precondition", "").strip(),
        "steps": steps,
        "expected_result": values.get("expected_result", "").strip(),
        "tags": tags,
        "owner": values.get("owner", "").strip(),
        "description": values.get("description", "").strip(),
    }
    return result


# ================================================================ 导入：执行
def _ensure_module(project, path_text: str, cache: dict) -> Module | None:
    """按「A/B/C」路径逐级取或建模块（不存在则自动创建）。"""
    parent = None
    for name in _split_module_path(path_text):
        cache_key = (parent.pk if parent else 0, name)
        module = cache.get(cache_key)
        if module is None:
            module = Module.objects.filter(project=project, parent=parent, name=name).first()
            if module is None:
                module = Module.objects.create(project=project, parent=parent, name=name)
            cache[cache_key] = module
        parent = module
    return parent


def _ensure_tags(project, names: list[str], cache: dict) -> list[int]:
    """标签按名取或建，返回标签 ID 列表。"""
    tag_ids = []
    for name in names:
        tag = cache.get(name)
        if tag is None:
            tag = Tag.objects.filter(project=project, name=name).first()
            if tag is None:
                tag = Tag.objects.create(project=project, name=name)
            cache[name] = tag
        tag_ids.append(tag.pk)
    return tag_ids


def import_cases(project, *, file_name: str, content: bytes, mapping: dict | None = None,
                 dry_run: bool = True, user=None, request=None) -> dict:
    """导入主流程：解析 → 映射 → 逐行校验 → 预览或确认入库。

    预览（dry_run=True）：返回 {total, valid, invalid, headers, mapping, rows}，不落库。
    确认（dry_run=False）：合法行入库，返回 {created, updated, skipped, failed}。
    """
    headers, raw_rows = parse_file(file_name, content)
    mapping = merge_mapping(headers, mapping or {})
    if not dry_run and "title" not in mapping:
        raise NanoAPIError("字段映射缺少「标题」列，无法导入")

    ctx = ImportContext(project)
    rows = [
        validate_row(project, line, headers, raw, mapping, ctx)
        for line, raw in enumerate(raw_rows, start=2)  # 第 1 行是表头
    ]

    valid = sum(1 for row in rows if not row.errors and row.action != "skip")
    payload = {
        "total": len(rows),
        "valid": valid,
        "invalid": len(rows) - valid,
        "headers": headers,
        "mapping": mapping,
        "rows": [
            {"line": row.line, "action": row.action, "errors": row.errors, "data": row.data}
            for row in rows
        ],
    }
    if dry_run:
        return payload

    payload.update(_persist_rows(project, rows, ctx, user=user, request=request))
    return payload


def merge_mapping(headers: list[str], mapping: dict) -> dict[str, str]:
    """合并自动猜测与用户映射；只保留合法字段名与真实存在的表头。"""
    merged = guess_mapping(headers)
    for field_name, header in (mapping or {}).items():
        if field_name in FIELD_LABELS and header:
            merged[field_name] = str(header)
    return merged


def _persist_rows(project, rows: list[RowResult], ctx: ImportContext, user=None, request=None) -> dict:
    """确认导入：合法行逐行落库（独立事务，单行失败不影响其余），非法行跳过并回报。"""
    created = updated = skipped = 0
    failed = []
    module_cache: dict = {}
    tag_cache: dict = {}

    for row in rows:
        if row.action == "skip":
            skipped += 1
            continue
        if row.errors:
            failed.append({"line": row.line, "errors": list(row.errors)})
            continue
        data, provided = row.data, row.provided
        try:
            with transaction.atomic():
                module = _ensure_module(project, data["module"], module_cache)
                tag_ids = _ensure_tags(project, data["tags"], tag_cache)
                owner = _resolve_owner(data["owner"], ctx.owner_cache)[0]
                if row.action == "create":
                    cases_service.create_case(
                        project,
                        {
                            "title": data["title"],
                            "module_id": module.pk if module else None,
                            "priority": data["priority"],
                            "case_type": data["case_type"],
                            "status": data["status"],
                            "precondition": data["precondition"],
                            "steps": data["steps"],
                            "expected_result": data["expected_result"],
                            "description": data["description"],
                            "tag_ids": tag_ids,
                            "owner_id": owner.pk if owner else None,
                        },
                        user=user,
                        request=request,
                    )
                    created += 1
                else:
                    case = TestCase.objects.get(pk=row.case_id)
                    # 更新行只覆盖单元格有值的字段，空单元格保留原值
                    update_data = {
                        "title": data["title"],
                        "steps": data["steps"],
                        "change_summary": "导入更新",
                        "updated_at": case.updated_at,
                    }
                    for key in ("precondition", "description", "expected_result", "priority", "case_type", "status"):
                        if provided.get(key):
                            update_data[key] = data[key]
                    if provided.get("module"):
                        update_data["module_id"] = module.pk
                    if provided.get("owner"):
                        update_data["owner_id"] = owner.pk
                    if provided.get("tags"):
                        update_data["tag_ids"] = tag_ids
                    cases_service.update_case(case, update_data, user=user, request=request)
                    updated += 1
        except Exception as exc:  # noqa: BLE001 - 单行失败需继续导入其余行
            failed.append({"line": row.line, "errors": [f"第 {row.line} 行：导入失败（{exc}）"]})

    return {"created": created, "updated": updated, "skipped": skipped, "failed": failed}
