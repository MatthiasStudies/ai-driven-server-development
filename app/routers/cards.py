"""Endpoints for managing cards."""

from collections.abc import Sequence
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud
from app.crud import StaleVersionError
from app.db import get_db
from app.models import Card
from app.schemas import CardCreate, CardRead, CardUpdate

router = APIRouter(prefix="/cards", tags=["cards"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CardRead,
    summary="Create a card",
)
def create_card(data: CardCreate, session: Session = Depends(get_db)) -> Card:
    """Create a new card in an existing binder."""
    binder = crud.get_binder(session, data.binder_id)
    if binder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Binder not found"
        )
    return crud.create_card(session, data)


@router.get("", response_model=list[CardRead], summary="List cards")
def list_cards(
    *,
    session: Session = Depends(get_db),
    binder_id: int | None = Query(
        default=None, description="Only cards in this binder."
    ),
    name: str | None = Query(
        default=None,
        max_length=100,
        description="Case-insensitive substring filter on the card name.",
    ),
    set_name: str | None = Query(
        default=None,
        max_length=100,
        description="Case-insensitive substring filter on the set name.",
    ),
    rarity: str | None = Query(
        default=None,
        max_length=50,
        description="Case-insensitive exact filter on the rarity.",
    ),
    variant: str | None = Query(
        default=None,
        max_length=50,
        description="Case-insensitive exact filter on the variant.",
    ),
    acquired_from: date | None = Query(
        default=None, description="Only cards acquired on or after this date."
    ),
    acquired_to: date | None = Query(
        default=None, description="Only cards acquired on or before this date."
    ),
    order_by: crud.CardOrderBy | None = Query(
        default=None,
        description="Field to order by. Defaults to insertion order.",
    ),
    order: crud.SortOrder = Query(default="asc", description="Sort direction."),
    limit: int = Query(default=50, ge=1, le=100, description="Page size."),
    offset: int = Query(default=0, ge=0, description="Number of items to skip."),
) -> Sequence[Card]:
    """List cards with optional filtering, ordering and pagination."""
    return crud.list_cards(
        session,
        binder_id=binder_id,
        name=name,
        set_name=set_name,
        rarity=rarity,
        variant=variant,
        acquired_from=acquired_from,
        acquired_to=acquired_to,
        order_by=order_by,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.get("/{card_id}", response_model=CardRead, summary="Get a card")
def get_card(card_id: int, session: Session = Depends(get_db)) -> Card:
    """Return a single card including its certificate if graded."""
    card = crud.get_card_with_certificate(session, card_id)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Card not found"
        )
    return card


@router.put(
    "/{card_id}",
    response_model=CardRead,
    summary="Update a card",
    responses={409: {"description": "Version conflict (stale version)"}},
)
def update_card(
    card_id: int, data: CardUpdate, session: Session = Depends(get_db)
) -> Card:
    """Partially update a card; the version must match the last read."""
    card = crud.get_card_with_certificate(session, card_id)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Card not found"
        )
    if data.binder_id is not None and crud.get_binder(session, data.binder_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Binder not found"
        )
    try:
        return crud.update_card(session, card, data)
    except StaleVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.delete(
    "/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a card",
    responses={
        204: {"description": "Card deleted (its certificate cascades)."},
        409: {"description": "Version conflict (stale version)"},
    },
)
def delete_card(
    card_id: int,
    *,
    version: int = Query(
        gt=0,
        description=(
            "Expected version from the last GET; a 409 is returned if the "
            "card changed since then."
        ),
    ),
    session: Session = Depends(get_db),
) -> None:
    """Delete a card; the version must match the last read."""
    card = crud.get_card_with_certificate(session, card_id)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Card not found"
        )
    try:
        crud.delete_card(session, card, version)
    except StaleVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
