from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.routers import downloads, generate, library, models, system
from app.services import registry
from app.services.inference.errors import OutOfMemoryError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

config.ensure_dirs()
try:
    registry.rescan()
except Exception:
    logger.exception("Library re-scan on startup failed; continuing with stored classifications")

app = FastAPI(title="TrulyOpen Workbench")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(downloads.router, prefix="/api")
app.include_router(library.router, prefix="/api")
app.include_router(generate.router, prefix="/api")


@app.exception_handler(OutOfMemoryError)
def handle_oom(request: Request, exc: OutOfMemoryError) -> JSONResponse:
    return JSONResponse(status_code=507, content={"detail": str(exc)})


@app.exception_handler(Exception)
def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"Internal error: {exc}"})


if config.FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
