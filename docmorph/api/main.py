from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from docmorph import __version__
from docmorph.api.jobs import JobManager
from docmorph.api.routes import router
from docmorph.api.storage import Storage
from docmorph.config import Settings, settings
from docmorph.core.engine import Engine
from docmorph.core.errors import DocMorphError
from docmorph.core.registry import Registry
from docmorph.engines import default_engines

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(config: Settings = settings, engines: list[Engine] | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        manager = JobManager(
            registry=Registry(engines if engines is not None else default_engines()),
            storage=Storage(config.data_dir, config.max_upload_mb),
            workers=config.workers,
            ttl_hours=config.ttl_hours,
        )
        manager.start()
        app.state.manager = manager
        yield
        manager.shutdown()

    app = FastAPI(title="DocMorph", version=__version__, lifespan=lifespan)

    @app.exception_handler(DocMorphError)
    async def docmorph_error(_: Request, exc: DocMorphError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content={"detail": exc.message, "error": exc.to_dict()})

    app.include_router(router)
    app.mount("/", StaticFiles(directory=_WEB_DIR, html=True), name="web")
    return app


app = create_app()
