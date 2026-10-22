"""FastAPI application for the TCG card collection server."""

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import db
from app.routers import binders, cards, certificates, search
from app.schemas import HealthStatus

app = FastAPI(
    title="tcg-card-stack",
    version="0.1.0",
    description="A TCG card collection management server.",
    openapi_tags=[
        {"name": "meta", "description": "Service health and metadata."},
    ],
)


app.include_router(binders.router)
app.include_router(cards.router)
app.include_router(certificates.router)
app.include_router(search.router)


@app.get(
    "/health",
    tags=["meta"],
    summary="Health check",
    response_model=HealthStatus,
    responses={503: {"description": "Database is unavailable"}},
)
def read_health(session: Session = Depends(db.get_db)) -> HealthStatus:
    """Report service and database health."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    return HealthStatus(status="ok", database="up")
