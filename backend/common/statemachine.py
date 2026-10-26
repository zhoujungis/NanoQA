"""状态机（§50）：Service 层校验状态转移，非法转移抛 InvalidTransitionError。

D5 决策：在文档链式转移基础上允许必要的回退转移（Deprecated→Active、
Closed→Reopened、Rejected→Open），贴合真实 QA 流程。
"""
from common.exceptions import InvalidTransitionError

# TestCase: draft → active → deprecated → archived
TESTCASE_TRANSITIONS = {
    "draft": {"active", "archived"},
    "active": {"deprecated", "archived", "draft"},
    "deprecated": {"active", "archived"},
    "archived": {"active"},
}

# TestPlan: draft → ready → running → completed
TESTPLAN_TRANSITIONS = {
    "draft": {"ready", "cancelled"},
    "ready": {"draft", "running", "cancelled"},
    "running": {"completed", "cancelled"},
    "completed": {"running"},  # 允许再次执行（回归）
    "cancelled": {"draft"},
}

# Defect: Open → In Progress → Resolved → Closed
DEFECT_TRANSITIONS = {
    "Open": {"In Progress", "Rejected", "Duplicate", "Closed"},
    "In Progress": {"Resolved", "Open", "Rejected", "Duplicate"},
    "Resolved": {"Closed", "Reopened", "In Progress"},
    "Reopened": {"In Progress", "Resolved", "Open"},
    "Closed": {"Reopened"},
    "Rejected": {"Open"},
    "Duplicate": {"Open"},
}

# Requirement: draft → ready → in_progress → done
REQUIREMENT_TRANSITIONS = {
    "draft": {"ready", "cancelled"},
    "ready": {"draft", "in_progress", "cancelled"},
    "in_progress": {"done", "ready", "cancelled"},
    "done": {"in_progress"},
    "cancelled": {"draft"},
}

TABLES = {
    "testcase": TESTCASE_TRANSITIONS,
    "testplan": TESTPLAN_TRANSITIONS,
    "defect": DEFECT_TRANSITIONS,
    "requirement": REQUIREMENT_TRANSITIONS,
}


def validate_transition(entity: str, from_status: str, to_status: str):
    """校验状态转移；返回 None。非法转移抛 InvalidTransitionError(40004)。"""
    if from_status == to_status:
        return
    table = TABLES.get(entity)
    if table is None:
        raise InvalidTransitionError(f"未知状态机: {entity}")
    allowed = table.get(from_status)
    if allowed is None:
        raise InvalidTransitionError(f"未知状态: {from_status}")
    if to_status not in allowed:
        raise InvalidTransitionError(
            f"状态不能从 {from_status} 变更为 {to_status}"
        )
