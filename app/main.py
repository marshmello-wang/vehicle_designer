from __future__ import annotations

import os
import logging
import time
from fastapi import FastAPI, Request
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
