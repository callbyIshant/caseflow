from secrets import token_hex

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import get_settings
from app.core.errors import error_response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.request_id = f"req_{token_hex(12)}"
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("origin") not in get_settings().trusted_origins:
                rejection = error_response(
                    request,
                    403,
                    "ORIGIN_INVALID",
                    "This request origin is not allowed.",
                )
                return self._apply_headers(request, rejection)
        response = await call_next(request)
        return self._apply_headers(request, response)

    @staticmethod
    def _apply_headers(request: Request, response: Response) -> Response:
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        if request.url.path.startswith("/docs"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data:; "
                "font-src 'self' https://cdn.jsdelivr.net; connect-src 'self'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
                "form-action 'self'"
            )

        if get_settings().environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        elif request.url.path == "/" or request.url.path.startswith(("/demo", "/app/", "/agent/")):
            response.headers["Cache-Control"] = "no-cache"
        return response
