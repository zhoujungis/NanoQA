"""异步任务抽象：v0.1 同步执行，v0.2 接 Celery worker 时切换实现。"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def run_async(task_name: str, fn, *args, **kwargs):
    """执行后台任务。NANOQA_ASYNC=0（默认）时同步执行并返回结果。"""
    if getattr(settings, "NANOQA_ASYNC", False):  # pragma: no cover - Celery v0.2 接入点
        logger.info("dispatch async task %s", task_name)
        return fn(*args, **kwargs)
    logger.debug("run task %s synchronously", task_name)
    return fn(*args, **kwargs)
