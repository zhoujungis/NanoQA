"""AI 用例生成 / 边界扩展（§39/§43）：Prompt 模板 + Provider + Schema 二次校验。"""
import json

from apps.ai.services import prompts
from apps.ai.services.schema import GENERATE_SCHEMA, validate_generated_cases


def generate_cases(provider, *, title: str, description: str, count: int, include_edge_cases: bool,
                   include_security: bool, include_compatibility: bool) -> dict:
    context = {
        "task": "generate_testcases",
        "title_hint": title,
        "title": title,
        "description": description,
        "count": count,
        "include_edge_cases": include_edge_cases,
        "include_security": include_security,
        "include_compatibility": include_compatibility,
    }
    prompt = prompts.load_prompt(
        "testcase_generate",
        title=title,
        description=description or "（未提供描述）",
        count=count,
        include_edge_cases=include_edge_cases,
        include_security=include_security,
        include_compatibility=include_compatibility,
        context_json=_json(context),
    )
    raw = provider.complete(prompt, schema=GENERATE_SCHEMA)
    return {"cases": validate_generated_cases(raw)}


def expand_edge_cases(provider, *, title: str, description: str, count: int = 5) -> dict:
    context = {
        "task": "expand_edge_cases",
        "title_hint": title,
        "title": title,
        "description": description,
        "count": count,
    }
    prompt = prompts.load_prompt(
        "testcase_generate",
        title=title,
        description=description or "（未提供描述）",
        count=count,
        include_edge_cases=True,
        include_security=False,
        include_compatibility=False,
        context_json=_json(context),
    )
    raw = provider.complete(prompt, schema=GENERATE_SCHEMA)
    return {"cases": validate_generated_cases(raw)}


def _json(context: dict) -> str:
    return json.dumps(context, ensure_ascii=False)
