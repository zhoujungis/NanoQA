"""业务错误码与统一异常处理（§44）。"""
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from common.renderers import envelope

logger = logging.getLogger(__name__)

# 业务错误码
CODE_SUCCESS = 0
CODE_PERMISSION_DENIED = 40001
CODE_UNAUTHENTICATED = 40002
CODE_CONFLICT = 40003          # 乐观锁冲突
CODE_INVALID_TRANSITION = 40004  # 状态机非法转移
CODE_NOT_FOUND = 40005
CODE_VALIDATION_ERROR = 40006
CODE_BUSINESS_CONFLICT = 40007  # 业务规则冲突（如模块仍有用例）
CODE_SERVER_ERROR = 50000


class NanoAPIError(Exception):
    """业务异常基类：Service 层抛出，异常处理器统一转换。"""

    status_code = status.HTTP_400_BAD_REQUEST
    code = CODE_VALIDATION_ERROR

    def __init__(self, message: str, code: int | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(NanoAPIError):
    status_code = status.HTTP_404_NOT_FOUND
    code = CODE_NOT_FOUND


class PermissionDeniedError(NanoAPIError):
    status_code = status.HTTP_403_FORBIDDEN
    code = CODE_PERMISSION_DENIED


class OptimisticLockError(NanoAPIError):
    status_code = status.HTTP_409_CONFLICT
    code = CODE_CONFLICT


class InvalidTransitionError(NanoAPIError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = CODE_INVALID_TRANSITION


class BusinessConflictError(NanoAPIError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = CODE_BUSINESS_CONFLICT


def nano_exception_handler(exc, context):
    response = exception_handler(exc, context)
    request = context.get("request")
    request_id = getattr(request, "request_id", None) if request else None

    if response is not None:
        # 映射 DRF 标准异常 → 业务码
        from rest_framework.exceptions import NotAuthenticated, AuthenticationFailed, PermissionDenied, ValidationError, NotFound

        if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
            code, message = CODE_UNAUTHENTICATED, "未认证或登录已过期"
        elif isinstance(exc, PermissionDenied):
            code, message = CODE_PERMISSION_DENIED, "权限不足"
        elif isinstance(exc, NotFound):
            code, message = CODE_NOT_FOUND, "资源不存在"
        elif isinstance(exc, ValidationError):
            code, message = CODE_VALIDATION_ERROR, _format_validation_error(response.data)
        else:
            code, message = CODE_VALIDATION_ERROR, str(exc)

        response.data = envelope(code, message, {"detail": response.data, "request_id": request_id})
        return response

    if isinstance(exc, NanoAPIError):
        logger.info("business error: %s", exc.message)
        return Response(
            envelope(exc.code, exc.message, {"request_id": request_id}),
            status=exc.status_code,
        )

    logger.exception("unhandled error, request_id=%s", request_id)
    return Response(
        envelope(CODE_SERVER_ERROR, "服务器内部错误", {"request_id": request_id}),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _format_validation_error(data) -> str:
    if isinstance(data, dict):
        if "detail" in data and isinstance(data["detail"], str):
            return data["detail"]
        parts = []
        for key, value in data.items():
            parts.append(f"{key}: {value[0] if isinstance(value, list) and value else value}")
        return "；".join(parts) if parts else "参数校验失败"
    if isinstance(data, list) and data:
        return str(data[0])
    return "参数校验失败"
