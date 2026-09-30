from pathlib import Path
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ExceptionHandler

from app.core.config import get_settings
from app.core.db import database_is_ready
from app.core.errors import (
    ApiError,
    api_exception_handler,
    error_response,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.middleware import SecurityHeadersMiddleware
from app.features.auth.router import router as auth_router

settings = get_settings()
app = FastAPI(
    title="CaseFlow API",
    summary="Northstar Services customer support ticketing API",
    description="A portfolio demonstration using synthetic support data.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_exception_handler(StarletteHTTPException, cast(ExceptionHandler, http_exception_handler))
app.add_exception_handler(RequestValidationError, cast(ExceptionHandler, validation_exception_handler))
app.add_exception_handler(Exception, unhandled_exception_handler)
app.add_exception_handler(ApiError, cast(ExceptionHandler, api_exception_handler))
app.include_router(auth_router)


@app.get("/health/live", tags=["health"])
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"], response_model=None)
def health_ready(request: Request) -> dict[str, str] | JSONResponse:
    if not database_is_ready():
        return error_response(
            request,
            503,
            "SERVICE_UNAVAILABLE",
            "The service is temporarily unavailable. Please retry shortly.",
        )
    return {"status": "ready"}


@app.get("/", include_in_schema=False, response_model=None)
def spa_root() -> FileResponse | JSONResponse:
    index_path = Path(__file__).parent / "static" / "index.html"
    if index_path.is_file():
        return FileResponse(index_path, headers={"Cache-Control": "no-cache"})
    return JSONResponse({"name": "CaseFlow", "status": "development", "frontend": "http://localhost:5173"})


@app.get("/{full_path:path}", include_in_schema=False, response_model=None)
def spa_fallback(full_path: str, request: Request) -> FileResponse:
    reserved_prefixes = ("api/", "docs", "openapi.json", "health/")
    if full_path.startswith(reserved_prefixes) or full_path.startswith("assets/"):
        raise StarletteHTTPException(status_code=404)
    index_path = Path(__file__).parent / "static" / "index.html"
    if index_path.is_file():
        return FileResponse(index_path, headers={"Cache-Control": "no-cache"})
    raise StarletteHTTPException(status_code=404)
