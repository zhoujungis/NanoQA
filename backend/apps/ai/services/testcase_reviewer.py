"""AI 用例评审（§41）：输出 {score, issues, suggestions} 并落 AITask。"""
import json

from apps.ai.services import prompts
from apps.ai.services.schema import REVIEW_SCHEMA, validate_review_output
from apps.testcases.models import TestCase, TestCaseVersion


def review_case(provider, test_case: TestCase) -> dict:
    version = TestCaseVersion.objects.filter(test_case=test_case).order_by("-version").first()
    steps = version.steps if version else []
    expected_result = version.expected_result if version else ""
    precondition = version.precondition if version else ""
    steps_text = "；".join(
        f"{step.get('order', index)}.{step.get('action', '')} → {step.get('expected', '')}"
        for index, step in enumerate(steps, start=1)
    )
    context = {
        "task": "review_testcase",
        "title": test_case.title,
        "precondition": precondition,
        "steps": steps,
        "expected_result": expected_result,
    }
    prompt = prompts.load_prompt(
        "testcase_review",
        title=test_case.title,
        precondition=precondition or "（未填写）",
        steps_text=steps_text or "（无步骤）",
        expected_result=expected_result or "（未填写）",
        context_json=json.dumps(context, ensure_ascii=False),
    )
    raw = provider.complete(prompt, schema=REVIEW_SCHEMA)
    return validate_review_output(raw)
