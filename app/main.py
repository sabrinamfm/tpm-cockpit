from fastapi import FastAPI

from app.api.routes.dependencies import router as dependencies_router
from app.api.routes.health import router as health_router
from app.api.routes.milestones import router as milestones_router
from app.api.routes.program_statuses import router as program_statuses_router
from app.api.routes.programs import router as programs_router
from app.api.routes.relationships import router as relationships_router
from app.api.routes.risks import router as risks_router
from app.api.routes.status_reports import router as status_reports_router
from app.api.routes.source_types import router as source_types_router
from app.api.routes.ui import router as ui_router
from app.api.routes.work_items import router as work_items_router


def create_app() -> FastAPI:
    app = FastAPI(title="TPM Cockpit", version="0.1.0")
    app.include_router(ui_router)
    app.include_router(health_router)
    app.include_router(milestones_router)
    app.include_router(program_statuses_router)
    app.include_router(programs_router)
    app.include_router(relationships_router)
    app.include_router(risks_router)
    app.include_router(status_reports_router)
    app.include_router(source_types_router)
    app.include_router(work_items_router)
    app.include_router(dependencies_router)
    return app


app = create_app()
