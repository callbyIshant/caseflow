import logging
from collections.abc import Mapping

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = dict(headers or {})


def request_id_for(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        request_id = "req_unavailable"
    return request_id


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
                "request_id": request_id_for(request),
            }
        },
        headers=dict(headers or {}),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        code, message = "NOT_FOUND", "The requested resource was not found."
    elif exc.status_code == 405:
        code, message = "METHOD_NOT_ALLOWED", "This method is not allowed for the requested resource."
    elif exc.status_code == 413:
        code, message = "REQUEST_TOO_LARGE", "The request exceeds the allowed size."
    else:
        code, message = "REQUEST_ERROR", "The request could not be completed."
    return error_response(request, exc.status_code, code, message, headers=exc.headers)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details: list[dict[str, str]] = []
    for error in exc.errors():
        location = error.get("loc", ())
        field = ".".join(str(part) for part in location if part not in {"body", "query", "path"})
        details.append({"field": field or "request", "issue": "The supplied value is invalid."})
    return error_response(
        request,
        422,
        "VALIDATION_ERROR",
        "Please correct the highlighted fields.",
        details,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None) or request.url.path
    logging.getLogger("caseflow.request").exception(
        "Unhandled request failure",
        extra={
            "fields": {
                "event": "request_error",
                "request_id": request_id_for(request),
                "route": route_path,
                "error_type": type(exc).__name__,
            }
        },
    )
    return error_response(
        request,
        500,
        "INTERNAL_ERROR",
        "The service could not complete this request. Please try again.",
    )


async def api_exception_handler(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(request, exc.status_code, exc.code, exc.message, headers=exc.headers)
