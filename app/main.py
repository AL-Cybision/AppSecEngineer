import json
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import get_settings
from app.routers import admin, auth, expenses, profile

logging.basicConfig(level=logging.INFO, format="%(message)s")
security_logger = logging.getLogger("expenseguard.security")


class HealthAwareTrustedHostMiddleware:
    """Allow private load-balancer health probes without weakening application routes."""

    def __init__(self, app: ASGIApp, allowed_hosts: list[str]) -> None:
        self.app = app
        self.trusted_hosts = TrustedHostMiddleware(app, allowed_hosts=allowed_hosts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") == "/health":
            await self.app(scope, receive, send)
            return
        await self.trusted_hosts(scope, receive, send)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield


def problem_response(
    request: Request, *, status_code: int, title: str, detail: str, code: str
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        content={
            "type": f"https://expenseguard.example/problems/{code}",
            "title": title,
            "status": status_code,
            "detail": detail,
            "code": code,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Security-focused expense and receipt approval API",
        lifespan=lifespan,
    )
    application.add_middleware(
        HealthAwareTrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts,
    )

    @application.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    @application.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            code = str(exc.detail.get("code", "request_failed"))
            detail = str(exc.detail.get("message", "Request failed"))
        else:
            code = "request_failed"
            detail = str(exc.detail)
        if exc.status_code in {401, 403} or code in {
            "file_too_large",
            "empty_file",
            "unsupported_file",
        }:
            security_logger.warning(
                json.dumps(
                    {
                        "event": "security_event",
                        "action": "request.rejected",
                        "outcome": "failure",
                        "reason": code,
                        "path": request.url.path,
                        "source_ip": request.client.host if request.client else None,
                        "request_id": getattr(request.state, "request_id", None),
                    }
                )
            )
        response = problem_response(
            request,
            status_code=exc.status_code,
            title="Request failed",
            detail=detail,
            code=code,
        )
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return problem_response(
            request,
            status_code=422,
            title="Validation failed",
            detail="The request did not satisfy the API schema",
            code="validation_failed",
        )

    @application.get("/health", tags=["operations"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(auth.router)
    application.include_router(profile.router)
    application.include_router(expenses.router)
    application.include_router(admin.router)
    return application


app = create_app()
