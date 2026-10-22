"""Pydantic schemas for API requests and responses."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class CardCreate(BaseModel):
    """Request schema for creating a card."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "binder_id": 1,
                    "name": "Gengar",
                    "set_name": "Fossil",
                    "collector_number": "5/62",
                    "rarity": "Holo Rare",
                    "variant": "1st Edition",
                    "acquired_at": "2024-01-15",
                }
            ]
        }
    )

    binder_id: int = Field(gt=0, examples=[1])
    name: str = Field(min_length=1, max_length=100, examples=["Gengar"])
    set_name: str = Field(min_length=1, max_length=100, examples=["Fossil"])
    collector_number: str = Field(min_length=1, max_length=20, examples=["5/62"])
    rarity: str = Field(min_length=1, max_length=50, examples=["Holo Rare"])
    variant: str = Field(default="Standard", max_length=50, examples=["1st Edition"])
    acquired_at: date | None = Field(default=None, examples=["2024-01-15"])

    @field_validator("acquired_at")
    @classmethod
    def validate_acquired_at_not_future(cls, value: date | None) -> date | None:
        """Reject acquisition dates in the future."""
        if value is not None and value > date.today():
            raise ValueError("acquired_at cannot be in the future")
        return value


class CardUpdate(BaseModel):
    """Request schema for partially updating a card.

    Fields left out keep their current values.
    """

    binder_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    set_name: str | None = Field(default=None, min_length=1, max_length=100)
    collector_number: str | None = Field(default=None, min_length=1, max_length=20)
    rarity: str | None = Field(default=None, min_length=1, max_length=50)
    variant: str | None = Field(default=None, max_length=50)
    acquired_at: date | None = None

    @field_validator("acquired_at")
    @classmethod
    def validate_acquired_at_not_future(cls, value: date | None) -> date | None:
        """Reject acquisition dates in the future."""
        if value is not None and value > date.today():
            raise ValueError("acquired_at cannot be in the future")
        return value


class SearchResultItem(BaseModel):
    """A single quicksearch hit with its fuzzy match score (0-100)."""

    card: CardRead
    binder_name: str
    score: float
