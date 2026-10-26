"""LLM Provider 抽象（§67）。

- BaseLLMProvider.complete(prompt, schema) -> dict：所有 AI 能力统一走结构化输出。
- MockLLMProvider：离线规则化生成，基于输入需求/用例标题产出合理结构化 JSON。
- OpenAICompatibleProvider：真实网关桩，读 NANOQA_LLM_API_KEY，未配置抛"未配置 LLM Provider"。
"""
import json
import os

from common.exceptions import NanoAPIError

CONTEXT_MARKER = "[CONTEXT]"


class BaseLLMProvider:
    name = "base"

    def complete(self, prompt: str, schema: dict | None = None) -> dict:
        raise NotImplementedError


def extract_context(prompt: str) -> dict:
    """Prompt 末尾携带 [CONTEXT] JSON 块，Provider 用它做规则化生成。"""
    if CONTEXT_MARKER not in prompt:
        return {}
    raw = prompt.split(CONTEXT_MARKER, 1)[1].strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


class MockLLMProvider(BaseLLMProvider):
    """离线 Mock：规则化生成结构化 JSON，保证全流程可离线验收。"""

    name = "mock"

    def complete(self, prompt: str, schema: dict | None = None) -> dict:
        context = extract_context(prompt)
        task = context.get("task", "")
        if task in ("generate_testcases", "expand_edge_cases"):
            return self._cases(context)
        if task == "review_testcase":
            return self._review(context)
        if task == "analyze_requirement":
            return self._analyze_requirement(context)
        if task == "analyze_defect":
            return self._analyze_defect(context)
        return {}

    # ------------------------------------------------------------- 用例生成
    def _cases(self, context: dict) -> dict:
        hint = context.get("title_hint") or context.get("title") or "核心功能"
        expand = context.get("task") == "expand_edge_cases"
        try:
            count = int(context.get("count") or (5 if expand else 10))
        except (TypeError, ValueError):
            count = 10
        count = max(1, min(count, 50))

        scenarios = self._scenarios(context, expand=expand)
        cases = []
        for index in range(count):
            suffix, priority, case_type = scenarios[index % len(scenarios)]
            title = f"【{hint}】{suffix}"
            if index >= len(scenarios):
                title = f"{title}（{index + 1}）"
            cases.append({
                "title": title[:255],
                "priority": priority,
                "type": case_type,
                "precondition": f"用户已登录，具备{hint}相关操作权限",
                "steps": [
                    {"action": f"进入{hint}功能页面", "expected": "页面加载正常，无报错"},
                    {"action": f"执行{suffix}对应操作", "expected": "系统给出明确反馈"},
                    {"action": "检查数据与状态变化", "expected": "数据落库且状态正确"},
                ],
                "expected_result": f"{hint}的{suffix}符合预期",
            })
        return {"cases": cases}

    def _scenarios(self, context: dict, expand: bool) -> list[tuple[str, str, str]]:
        if expand:
            return [
                ("空值/缺省输入", "P1", "functional"),
                ("超长文本输入", "P2", "functional"),
                ("边界数值校验", "P1", "functional"),
                ("并发重复操作", "P2", "functional"),
                ("异常中断恢复", "P2", "exploratory"),
            ]
        scenarios = [
            ("正常流程验证", "P1", "functional"),
            ("必填参数校验", "P1", "functional"),
            ("异常输入处理", "P2", "functional"),
            ("重复提交防护", "P2", "functional"),
        ]
        if context.get("include_edge_cases"):
            scenarios.append(("边界值验证", "P1", "functional"))
        if context.get("include_security"):
            scenarios.append(("越权访问拦截", "P1", "security"))
        if context.get("include_compatibility"):
            scenarios.append(("多端兼容性验证", "P2", "compatibility"))
        return scenarios

    # ------------------------------------------------------------- 用例评审
    def _review(self, context: dict) -> dict:
        score, issues, suggestions = 100, [], []
        steps = context.get("steps") or []
        if len(steps) < 2:
            score -= 25
            issues.append({"severity": "high", "message": "测试步骤少于 2 条，覆盖不足"})
            suggestions.append("补充前置操作与验证步骤，至少覆盖操作与校验两步")
        elif len(steps) < 3:
            score -= 10
            issues.append({"severity": "medium", "message": "测试步骤偏少，建议补充验证点"})
            suggestions.append("增加数据校验或状态确认步骤")
        if not str(context.get("expected_result") or "").strip():
            score -= 15
            issues.append({"severity": "high", "message": "缺少预期结果，无法判定通过标准"})
            suggestions.append("为用例补充明确、可验证的预期结果")
        if not str(context.get("precondition") or "").strip():
            score -= 10
            issues.append({"severity": "medium", "message": "缺少前置条件"})
            suggestions.append("补充前置条件，明确初始数据与账号状态")
        if len(str(context.get("title") or "").strip()) < 6:
            score -= 10
            issues.append({"severity": "low", "message": "标题描述过短，可读性不足"})
            suggestions.append("标题补充场景与预期，便于检索")
        if not issues:
            suggestions.append("用例结构完整，可考虑补充边界值与异常场景")
        return {"score": max(0, min(100, score)), "issues": issues, "suggestions": suggestions}

    # ------------------------------------------------------------- 需求/缺陷分析
    def _analyze_requirement(self, context: dict) -> dict:
        title = context.get("title") or "需求"
        description = str(context.get("description") or "")
        cases = self._cases({
            "task": "generate_testcases",
            "title_hint": title,
            "count": 3,
            "include_edge_cases": True,
        })["cases"]
        risks = [
            {"level": "medium", "message": "建议补充非功能需求（性能/安全）验收标准"},
        ]
        if not description.strip():
            risks.insert(0, {"level": "high", "message": "需求描述缺失，验收标准可能遗漏"})
        summary = f"需求「{title}」" + (
            f"核心范围：{description[:80]}" if description.strip() else "描述缺失，建议先补齐验收标准"
        )
        return {"summary": summary, "suggested_cases": cases, "risks": risks}

    def _analyze_defect(self, context: dict) -> dict:
        title = context.get("title") or "该缺陷"
        return {
            "possible_causes": [
                f"「{title}」相关逻辑分支处理不完整",
                "边界条件未覆盖导致异常路径触发",
                "依赖服务超时或异常返回未兜底",
            ],
            "suggestions": [
                "补充日志与复现步骤，缩小触发条件",
                "针对异常路径补充回归用例",
                "修复后关联用例回归验证",
            ],
            "related_case_ids": list(context.get("related_case_ids") or []),
        }


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI 兼容网关桩：未配置环境变量时抛业务异常（v0.2 接入真实调用）。"""

    name = "openai"

    def __init__(self):
        self.api_key = os.environ.get("NANOQA_LLM_API_KEY", "")
        self.base_url = os.environ.get("NANOQA_LLM_BASE_URL", "")
        self.model = os.environ.get("NANOQA_LLM_MODEL", "")

    def complete(self, prompt: str, schema: dict | None = None) -> dict:
        if not self.api_key:
            raise NanoAPIError("未配置 LLM Provider")
        raise NanoAPIError("LLM 网关调用将在 v0.2 接入")


def get_provider() -> BaseLLMProvider:
    if os.environ.get("NANOQA_LLM_API_KEY") or os.environ.get("NANOQA_LLM_PROVIDER", "").lower() == "openai":
        return OpenAICompatibleProvider()
    return MockLLMProvider()
