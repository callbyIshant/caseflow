from __future__ import annotations

import json
import logging
import sys
import time
import traceback
from secrets import token_hex

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings


class _RequestJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = getattr(record, "fields", {})
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname.lower(),
            "environment": get_settings().environment,
            **fields,
        }
        if record.exc_info is not None:
            payload["stack"] = "".join(traceback.format_tb(record.exc_info[2]))
        return json.dumps(payload, separators=(",", ":"))


_request_logger = logging.getLogger("caseflow.request")
if not _request_logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(_RequestJsonFormatter())
    _request_logger.addHandler(_handler)
    _request_logger.setLevel(logging.INFO)
    _request_logger.propagate = False


class SecurityHeadersMiddleware:
    """Apply same-origin, size, security-header, and request-log policy at the edge."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        request_id = f"req_{token_hex(12)}"
        scope.setdefault("state", {})["request_id"] = request_id
        settings = get_settings()
        path = request.url.path

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                extra_headers = self._headers(request, settings.environment == "production")
                extra_headers["X-Request-ID"] = request_id
                replaced_names = {name.lower().encode("latin-1") for name in extra_headers}
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() not in replaced_names
                ]
                for name, value in extra_headers.items():
                    headers.append((name.lower().encode("latin-1"), value.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        started = time.perf_counter()
        status_code = 500

        async def tracked_send(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send_with_headers(message)

        async def send_json_error(status: int, code: str, message: str, retry_after: str | None = None) -> None:
            headers = {"Retry-After": retry_after} if retry_after is not None else None
            response = JSONResponse(
                status_code=status,
                content={
                    "error": {
                        "code": code,
                        "message": message,
                        "details": [],
                        "request_id": request_id,
                    }
                },
                headers=headers,
            )
            await response(scope, receive, tracked_send)

        try:
            if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get(
                "origin"
            ) not in settings.trusted_origins:
                await send_json_error(
                    403, "ORIGIN_INVALID", "This request origin is not allowed."
                )
                return

            body = b""
            replay_receive = receive
            if path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                content_length = request.headers.get("content-length")
                if content_length is not None:
                    try:
                        declared_length = int(content_length)
                    except ValueError:
                        await send_json_error(400, "REQUEST_ERROR", "The request could not be completed.")
                        return
                    if declared_length > settings.max_request_bytes:
                        await send_json_error(
                            413,
                            "REQUEST_TOO_LARGE",
                            "The request exceeds the allowed size.",
                        )
                        return

                body_parts: list[bytes] = []
                body_size = 0
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    if message["type"] != "http.request":
                        continue
                    chunk = message.get("body", b"")
                    body_size += len(chunk)
                    if body_size > settings.max_request_bytes:
                        await send_json_error(
                            413,
                            "REQUEST_TOO_LARGE",
                            "The request exceeds the allowed size.",
                        )
                        return
                    body_parts.append(chunk)
                    if not message.get("more_body", False):
                        break
                body = b"".join(body_parts)
                supplied_content_type = request.headers.get("content-type")
                content_type = (
                    supplied_content_type.split(";", 1)[0].lower()
                    if supplied_content_type
                    else ""
                )
                if (body and not content_type) or (content_type and content_type != "application/json"):
                    await send_json_error(
                        415,
                        "UNSUPPORTED_MEDIA_TYPE",
                        "Send JSON using the application/json media type.",
                    )
                    return
                consumed = False

                async def replay_body() -> Message:
                    nonlocal consumed
                    if consumed:
                        return {"type": "http.disconnect"}
                    consumed = True
                    return {"type": "http.request", "body": body, "more_body": False}

                replay_receive = replay_body

            await self.app(scope, replay_receive, tracked_send)
        finally:
            if path not in {"/health/live", "/health/ready"}:
                route = scope.get("route")
                route_path = getattr(route, "path", None) or path
                _request_logger.info(
                    "http_request",
                    extra={
                        "fields": {
                            "event": "request_complete",
                            "request_id": request_id,
                            "method": request.method,
                            "route": route_path,
                            "status": status_code,
                            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                        }
                    },
                )

    @staticmethod
    def _headers(request: Request, production: bool) -> dict[str, str]:
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }
        if request.url.path.startswith("/docs"):
            headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data:; "
                "font-src 'self' https://cdn.jsdelivr.net; connect-src 'self'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
            )
        else:
            headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
                "form-action 'self'"
            )
        if production:
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith("/api/"):
            headers["Cache-Control"] = "no-store"
        elif request.url.path in {"/", "/index.html"} or request.url.path.startswith(
            ("/demo", "/app/", "/agent/")
        ):
            headers["Cache-Control"] = "no-cache"
        elif request.url.path.startswith("/assets/"):
            headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return headers
