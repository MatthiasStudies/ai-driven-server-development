"""Pydantic schemas for API requests and responses."""

from pydantic import BaseModel


class HealthStatus(BaseModel):
    """Response schema of the health endpoint."""

    status: str
    database: str
