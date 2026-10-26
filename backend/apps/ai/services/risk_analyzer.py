"""需求/缺陷风险分析（§66）：统一 risk_analysis 模板，输出结构化 JSON。"""
import json

from apps.ai.services import prompts
from apps.ai.services.schema import validate_analysis_output


def analyze_requirement(provider, requirement) -> dict:
    context = {
        "task": "analyze_requirement",
        "title": requirement.title,
        "description": requirement.description,
    }
    prompt = prompts.load_prompt(
        "risk_analysis",
        kind="需求",
        title=requirement.title,
        description=requirement.description or "（未提供描述）",
        output_hint='{"summary": "...", "suggested_cases": [...], "risks": [{"level": "high|medium|low", "message": "..."}]}',
        context_json=json.dumps(context, ensure_ascii=False),
    )
    raw = provider.complete(prompt)
    return validate_analysis_output(raw, ("summary", "suggested_cases", "risks"))


def analyze_defect(provider, defect, related_case_ids: list[int]) -> dict:
    context = {
        "task": "analyze_defect",
        "title": defect.title,
        "description": defect.description,
        "related_case_ids": related_case_ids,
    }
    prompt = prompts.load_prompt(
        "risk_analysis",
        kind="缺陷",
        title=defect.title,
        description=defect.description or "（未提供描述）",
        output_hint='{"possible_causes": [...], "suggestions": [...], "related_case_ids": [...]}',
        context_json=json.dumps(context, ensure_ascii=False),
    )
    raw = provider.complete(prompt)
    output = validate_analysis_output(raw, ("possible_causes", "suggestions", "related_case_ids"))
    output["related_case_ids"] = list(related_case_ids)
    return output
