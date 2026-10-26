"""AI 输出 JSON Schema 二次校验（§68）：模型输出只进 AITask，先过结构校验。"""
from apps.testcases.models import TestCase
from common.exceptions import CODE_VALIDATION_ERROR, NanoAPIError

VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}
VALID_TYPES = {choice[0] for choice in TestCase.TYPE_CHOICES}
VALID_SEVERITIES = {"high", "medium", "low"}

GENERATE_SCHEMA = {
    "type": "object",
    "properties": {
        "cases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "priority": {"type": "string", "enum": sorted(VALID_PRIORITIES)},
                    "type": {"type": "string", "enum": sorted(VALID_TYPES)},
                    "precondition": {"type": "string"},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"action": {"type": "string"}, "expected": {"type": "string"}},
                        },
                    },
                    "expected_result": {"type": "string"},
                },
            },
        }
    },
}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "issues": {"type": "array", "items": {"type": "object"}},
        "suggestions": {"type": "array", "items": {"type": "string"}},
    },
}


class SchemaValidationError(NanoAPIError):
    code = CODE_VALIDATION_ERROR


def validate_generated_cases(payload: dict) -> list[dict]:
    """校验生成用例结构：title/priority/type/steps(action,expected) 全部非空合法。"""
    if not isinstance(payload, dict):
        raise SchemaValidationError("AI 输出不是 JSON 对象")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SchemaValidationError("AI 输出缺少 cases 列表")

    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise SchemaValidationError(f"第 {index} 条用例不是 JSON 对象")
        title = case.get("title")
        if not isinstance(title, str) or not title.strip():
            raise SchemaValidationError(f"第 {index} 条用例 title 为空")
        if case.get("priority") not in VALID_PRIORITIES:
            raise SchemaValidationError(f"第 {index} 条用例 priority 非法: {case.get('priority')!r}")
        if case.get("type") not in VALID_TYPES:
            raise SchemaValidationError(f"第 {index} 条用例 type 非法: {case.get('type')!r}")
        steps = case.get("steps")
        if not isinstance(steps, list) or not steps:
            raise SchemaValidationError(f"第 {index} 条用例 steps 为空")
        for step_index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                raise SchemaValidationError(f"第 {index} 条用例第 {step_index} 步不是 JSON 对象")
            if not str(step.get("action") or "").strip():
                raise SchemaValidationError(f"第 {index} 条用例第 {step_index} 步 action 为空")
            if not str(step.get("expected") or "").strip():
                raise SchemaValidationError(f"第 {index} 条用例第 {step_index} 步 expected 为空")
    return cases


def validate_review_output(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise SchemaValidationError("AI 评审输出不是 JSON 对象")
    score = payload.get("score")
    if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
        raise SchemaValidationError(f"AI 评审 score 非法: {score!r}")
    issues = payload.get("issues")
    if not isinstance(issues, list):
        raise SchemaValidationError("AI 评审 issues 非法")
    for index, issue in enumerate(issues, start=1):
        if not isinstance(issue, dict) or not str(issue.get("message") or "").strip():
            raise SchemaValidationError(f"AI 评审第 {index} 条 issue 非法")
        if issue.get("severity") not in VALID_SEVERITIES:
            raise SchemaValidationError(f"AI 评审第 {index} 条 issue severity 非法")
    suggestions = payload.get("suggestions")
    if not isinstance(suggestions, list):
        raise SchemaValidationError("AI 评审 suggestions 非法")
    return {"score": score, "issues": issues, "suggestions": suggestions}


def validate_analysis_output(payload: dict, required_keys: tuple[str, ...]) -> dict:
    if not isinstance(payload, dict):
        raise SchemaValidationError("AI 分析输出不是 JSON 对象")
    for key in required_keys:
        if key not in payload:
            raise SchemaValidationError(f"AI 分析输出缺少字段: {key}")
    return payload
