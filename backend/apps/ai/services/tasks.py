"""AI 任务编排：AITask 生命周期（running→succeeded/failed）+ 成本记录（§69）。

坑 3：AI 输出只进 AITask.output_data，必须人工 accept 才转正式 TestCase。
"""
import json
import time

from django.db import transaction
from django.utils import timezone

from apps.ai.models import AITask
from apps.ai.services import llm
from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.projects.services.keys import next_key
from apps.testcases.models import TestCase, TestCaseVersion
from common.exceptions import BusinessConflictError, NanoAPIError


class AITaskFailed(NanoAPIError):
    """AI 任务执行失败：携带已落库的 AITask，供 API 返回 task_id。"""

    def __init__(self, message: str, task: AITask):
        super().__init__(message)
        self.task = task


def estimate_tokens(*payloads) -> int:
    size = sum(len(json.dumps(item, ensure_ascii=False)) for item in payloads if item is not None)
    return max(1, size // 4)


def run_task(*, project, user, task_type: str, input_data: dict, produce) -> AITask:
    """执行一次 AI 任务：produce(provider) 返回 output_data，失败落 status=failed + error。"""
    provider = llm.get_provider()
    task = AITask.objects.create(
        organization=project.organization,
        project=project,
        user=user,
        task_type=task_type,
        input_data=input_data,
        status=AITask.STATUS_RUNNING,
        model=provider.name,
    )
    started = time.perf_counter()
    try:
        output = produce(provider)
    except Exception as exc:  # noqa: BLE001 - 统一收口任务失败态
        task.status = AITask.STATUS_FAILED
        task.error = str(exc)
        task.duration = int((time.perf_counter() - started) * 1000)
        task.completed_at = timezone.now()
        task.save(update_fields=["status", "error", "duration", "completed_at"])
        if isinstance(exc, NanoAPIError):
            raise AITaskFailed(str(exc), task) from exc
        raise

    task.status = AITask.STATUS_SUCCEEDED
    task.output_data = output or {}
    task.tokens = estimate_tokens(input_data, task.output_data)
    task.duration = int((time.perf_counter() - started) * 1000)
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "output_data", "tokens", "duration", "completed_at"])
    return task


@transaction.atomic
def accept_task(task: AITask, user, request=None) -> list[TestCase]:
    """人工审核通过：output_data.cases 全部转正式 TestCase（draft + v1 版本），事务 + 审计。"""
    if task.output_data.get("accepted"):
        raise BusinessConflictError("该 AI 任务已审核入库，请勿重复操作")
    if task.status != AITask.STATUS_SUCCEEDED:
        raise NanoAPIError("仅成功的 AI 任务可以入库")
    cases = task.output_data.get("cases") or []
    if not cases:
        raise NanoAPIError("AI 任务没有可入库的用例")

    created = []
    for case in cases:
        test_case = TestCase.objects.create(
            organization=task.organization,
            project=task.project,
            case_key=next_key(task.project, "TC"),
            title=str(case.get("title", ""))[:255],
            description=str(case.get("description", "")),
            precondition=str(case.get("precondition", "")),
            priority=case.get("priority", "P1"),
            case_type=case.get("type", "functional"),
            status=TestCase.STATUS_DRAFT,
            creator=user,
            current_version=1,
        )
        steps = [
            {"order": index, "action": step.get("action", ""), "expected": step.get("expected", "")}
            for index, step in enumerate(case.get("steps") or [], start=1)
        ]
        TestCaseVersion.objects.create(
            test_case=test_case,
            version=1,
            title=test_case.title,
            description=test_case.description,
            precondition=test_case.precondition,
            steps=steps,
            expected_result=str(case.get("expected_result", "")),
            created_by=user,
            change_summary="AI 生成并人工审核通过",
        )
        AuditService.record(
            AuditLog.ACTION_CREATE, test_case, request=request, user=user,
            new_data={"case_key": test_case.case_key, "title": test_case.title, "source": "ai_task"},
        )
        created.append(test_case)

    task.output_data["accepted"] = True
    task.output_data["accepted_case_ids"] = [case.id for case in created]
    task.save(update_fields=["output_data"])
    AuditService.record(
        AuditLog.ACTION_UPDATE, task, request=request, user=user,
        object_ref=str(task.id), new_data={"accepted": True, "case_ids": [c.id for c in created]},
    )
    return created


@transaction.atomic
def reject_task(task: AITask, user, request=None) -> AITask:
    """人工拒绝：标记 rejected，不入库。"""
    if task.output_data.get("accepted"):
        raise BusinessConflictError("该 AI 任务已审核入库，无法拒绝")
    task.output_data["rejected"] = True
    task.save(update_fields=["output_data"])
    AuditService.record(
        AuditLog.ACTION_UPDATE, task, request=request, user=user,
        object_ref=str(task.id), new_data={"rejected": True},
    )
    return task
