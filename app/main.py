"""FastAPI application entry point."""

import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.openapi.utils import get_openapi
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import routes
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import get_logger

logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Cognito Auth API starting | region={}", settings.aws_region)
    yield
    logger.info("Cognito Auth API shutting down")


app = FastAPI(title="Cognito Auth API", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    logger.debug(
        "{method} {path} completed in {time:.4f}s | status={status}",
        method=request.method,
        path=request.url.path,
        time=process_time,
        status=response.status_code,
    )
    return response


@app.middleware("http")
async def add_no_store_headers(request: Request, call_next):
    # Auth responses contain tokens or PII — never let intermediaries cache them.
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    schema.setdefault("components", {})["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    }

    public_paths = {
        "/api/v1/signup",
        "/api/v1/confirm",
        "/api/v1/login",
        "/api/v1/refresh",
        "/api/v1/resend-confirmation",
        "/api/v1/forgot-password",
        "/api/v1/reset-password",
    }

    for path, path_item in schema.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        is_public = path in public_paths
        for method, operation in path_item.items():
            if method not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "options",
                "head",
                "trace",
            }:
                continue
            if not isinstance(operation, dict):
                continue
            operation["security"] = [] if is_public else [{"BearerAuth": []}]

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi

app.include_router(routes.router, prefix="/api/v1")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
