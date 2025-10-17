from __future__ import annotations

import os
import logging
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.routes.projects import router as projects_router
from app.routes.generate import router as generate_router
from app.routes.versions import router as versions_router


def _setup_logging() -> None:
    # Basic logging setup; level can be adjusted via ENV LOG_LEVEL
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def create_app() -> FastAPI:
    _setup_logging()
    app = FastAPI(title="Vehicle Designer API", version="0.1.0")

    logger = logging.getLogger("app.middleware")

    # CORS support (allow-all by default; override via env)
    origins_env = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
    methods_env = os.getenv("CORS_ALLOW_METHODS", "*").strip()
    headers_env = os.getenv("CORS_ALLOW_HEADERS", "*").strip()

    if origins_env == "*":
        allow_origins = ["*"]
    else:
        allow_origins = [o.strip() for o in origins_env.split(",") if o.strip()]

    allow_methods = ["*"] if methods_env == "*" else [m.strip().upper() for m in methods_env.split(",") if m.strip()]
    allow_headers = ["*"] if headers_env == "*" else [h.strip() for h in headers_env.split(",") if h.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.time()
        method = request.method
        path = request.url.path
        client = getattr(request.client, "host", "-") if getattr(request, "client", None) else "-"
        try:
            response = await call_next(request)
            status = getattr(response, "status_code", 0)
            return response
        finally:
            dur_ms = int((time.time() - start) * 1000)
            logger.info(
                "http_request method=%s path=%s status=%s duration_ms=%s client=%s",
                method,
                path,
                locals().get("status", 0),
                dur_ms,
                client,
            )
    app.include_router(projects_router)
    app.include_router(generate_router)
    app.include_router(versions_router)
    return app


app = create_app()
