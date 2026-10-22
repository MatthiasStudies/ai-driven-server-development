"""Pydantic schemas for API requests and responses."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthStatus(BaseModel):
    """Response schema of the health endpoint."""

    status: str
    database: str


class ErrorResponse(BaseModel):
    """Error payload returned with 4xx responses."""

    detail: str


# --- Binders ---


class BinderCreate(BaseModel):
    """Request schema for creating a binder."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"name": "Vintage Vault", "description": "High-value WOTC era holos"}
            ]
        }
    )

    name: str = Field(min_length=1, max_length=100, examples=["Vintage Vault"])
    description: str | None = Field(
        default=None, examples=["High-value WOTC era holos and graded slabs"]
    )


class BinderUpdate(BaseModel):
    """Request schema for partially updating a binder.

    Fields left out keep their current values.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class BinderRead(BaseModel):
    """Response schema for a binder."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    created_at: datetime


class BinderDetail(BinderRead):
    """Response schema for a binder including its cards."""

    cards: list["CardRead"]


# --- Cards ---


class CertificateRead(BaseModel):
    """Response schema for a grading certificate."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    grading_company: str
    cert_number: str
    grade: float
    graded_at: date


class CardRead(BaseModel):
    """Response schema for a card, embedding its certificate if graded."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    binder_id: int
    name: str
    set_name: str
    collector_number: str
    rarity: str
    variant: str
    acquired_at: date
    certificate: CertificateRead | None = None
