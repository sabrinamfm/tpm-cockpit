from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.programs import router as programs_router


def create_app() -> FastAPI:
    app = FastAPI(title="TPM Cockpit", version="0.1.0")
    app.include_router(health_router)
    app.include_router(programs_router)
    return app


app = create_app()
