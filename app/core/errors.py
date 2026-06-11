"""Unified error handling structures for the application."""

from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.core.provider_errors import (
    ProviderConfigError,
    ProviderError,
    ProviderResponseError,
    ProviderTimeoutError,
)

logger = get_logger(__name__)


class AppException(Exception):
    """Base application exception class."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppException):
    """Resource not found exception."""

    def __init__(self, resource: str, identifier: str | int | None = None) -> None:
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with id '{identifier}' not found"
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "identifier": str(identifier) if identifier else None},
        )


class ValidationError(AppException):
    """Validation error exception."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details or {},
        )


class DatabaseError(AppException):
    """Database operation error exception."""

    def __init__(
        self, message: str = "Database operation failed", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details or {},
        )


async def app_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle AppException and return JSON response."""
    if isinstance(exc, AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                error=exc.message,
                message=exc.message,
                code="application_error",
                details=exc.details,
                detail=exc.message,
            ),
        )
    # Fallback for unexpected exceptions
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_internal_error_payload(exc),
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle HTTPException and return JSON response."""
    if isinstance(exc, HTTPException):
        detail = exc.detail
        error = detail if isinstance(detail, str) else "HTTP error"
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                error=error,
                message=_http_user_message(exc.status_code, detail),
                code=_http_error_code(exc.status_code),
                details={},
                detail=detail,
            ),
        )
    # Fallback for unexpected exceptions
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_internal_error_payload(exc),
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle FastAPI/Pydantic request validation errors."""
    if not isinstance(exc, RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_internal_error_payload(exc),
        )

    raw_errors = exc.errors()
    fields = [_format_validation_error(error) for error in raw_errors]
    readable = "; ".join(f"{field['field']}: {field['message']}" for field in fields)
    message = "请求参数不正确"
    if readable:
        message = f"{message}：{readable}"

    return JSONResponse(
        status_code=422,
        content=_error_payload(
            error="Request validation failed",
            message=message,
            code="validation_error",
            details={"fields": fields},
            detail=[_safe_validation_detail(error) for error in raw_errors],
        ),
    )


async def provider_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle LLM/Embedding provider failures with actionable, non-secret messages."""
    if not isinstance(exc, ProviderError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_internal_error_payload(exc),
        )

    if isinstance(exc, ProviderConfigError):
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        code = "provider_config_error"
        message = "AI 服务配置错误，请联系管理员检查 API Key、模型名称或 Base URL。"
    elif isinstance(exc, ProviderTimeoutError):
        status_code = status.HTTP_504_GATEWAY_TIMEOUT
        code = "provider_timeout"
        message = "AI 服务响应超时，请稍后重试。"
    elif isinstance(exc, ProviderResponseError):
        status_code = status.HTTP_502_BAD_GATEWAY
        code = "provider_response_error"
        message = "AI 服务返回异常，请检查模型、额度、Base URL，或稍后重试。"
    else:
        status_code = status.HTTP_502_BAD_GATEWAY
        code = "provider_error"
        message = "AI 服务暂时不可用，请稍后重试。"

    logger.warning(
        "Provider error on %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=status_code,
        content=_error_payload(
            error=message,
            message=message,
            code=code,
            details={"provider": exc.provider, "type": type(exc).__name__},
            detail=message,
        ),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle generic exceptions and return JSON response."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_internal_error_payload(exc),
    )


def _error_payload(
    *,
    error: str,
    message: str,
    code: str,
    details: dict[str, Any],
    detail: Any,
) -> dict[str, Any]:
    return {
        "error": error,
        "message": message,
        "code": code,
        "details": details,
        "detail": detail,
    }


def _internal_error_payload(exc: Exception) -> dict[str, Any]:
    return _error_payload(
        error="Internal server error",
        message="服务器内部错误，请稍后重试；如果问题持续，请查看 API 日志。",
        code="internal_server_error",
        details={"type": type(exc).__name__},
        detail="Internal server error",
    )


def _http_error_code(status_code: int) -> str:
    codes = {
        status.HTTP_400_BAD_REQUEST: "bad_request",
        status.HTTP_401_UNAUTHORIZED: "unauthenticated",
        status.HTTP_403_FORBIDDEN: "forbidden",
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_409_CONFLICT: "conflict",
    }
    return codes.get(status_code, "http_error")


def _http_user_message(status_code: int, detail: Any) -> str:
    detail_text = detail if isinstance(detail, str) else ""
    if status_code == status.HTTP_401_UNAUTHORIZED:
        return "请先登录或重新登录后再试。"
    if status_code == status.HTTP_403_FORBIDDEN:
        if detail_text == "Inactive user":
            return "账号已被禁用，请联系管理员。"
        return detail_text or "当前账号没有权限执行此操作。"
    if status_code == status.HTTP_404_NOT_FOUND:
        return detail_text or "请求的资源不存在或你无权访问。"
    if status_code == status.HTTP_409_CONFLICT:
        return detail_text or "数据已存在，请换一个值后重试。"
    if status_code == status.HTTP_400_BAD_REQUEST:
        return detail_text or "请求参数不正确，请检查后重试。"
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        return "服务器内部错误，请稍后重试；如果问题持续，请查看 API 日志。"
    return detail_text or f"请求失败：HTTP {status_code}"


def _format_validation_error(error: dict[str, Any]) -> dict[str, str]:
    loc = error.get("loc", ())
    if isinstance(loc, tuple | list):
        parts = [str(part) for part in loc if str(part) not in {"body", "query", "path"}]
        field = ".".join(parts) if parts else "request"
    else:
        field = str(loc)
    message = str(error.get("msg") or "Invalid value")
    return {"field": field, "message": message}


def _safe_validation_detail(error: dict[str, Any]) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "type": str(error.get("type") or "value_error"),
        "loc": [str(part) for part in error.get("loc", ())],
        "msg": str(error.get("msg") or "Invalid value"),
    }
    if "input" in error:
        detail["input"] = _safe_json_value(error["input"])
    return detail


def _safe_json_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list | tuple):
        return [_safe_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _safe_json_value(item) for key, item in value.items()}
    return str(value)
